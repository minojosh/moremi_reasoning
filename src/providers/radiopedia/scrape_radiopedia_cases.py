import json
import time
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
import concurrent.futures
import threading
from tqdm import tqdm

# Thread-local storage for WebDriver instances
thread_local = threading.local()

def get_driver():
    """
    Get a thread-local WebDriver instance
    """
    if not hasattr(thread_local, "driver"):
        thread_local.driver = setup_driver()
    return thread_local.driver

def setup_driver():
    """
    Set up and return a Chrome WebDriver instance
    """
    chrome_options = Options()
    # Performance optimizations
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--blink-settings=imagesEnabled=true")
    
    # SSL error handling options
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--disable-web-security")
    
    # Create a new Chrome WebDriver instance
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set page load strategy to 'eager' - wait only until DOM is ready
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': os.getcwd()})
    
    return driver

def extract_series_from_study_section(driver, section, study_index):
    """
    Extract all series from a study section by interacting with the carousel
    """
    series_data = {}
    wait = WebDriverWait(driver, 10)
    
    try:
        # Look for the carousel header with image list items
        carousel_header = section.find_element(By.CSS_SELECTOR, "._StudyCarouselHeader_Container")
        image_list_items = carousel_header.find_elements(By.CSS_SELECTOR, "._StudyCarouselHeader_ImageListItem")
        
        print(f"Found {len(image_list_items)} series in study {study_index}")
        
        # Get the main image caption/findings for this study (applies to all series)
        study_caption = ""
        try:
            findings_div = section.find_element(By.CSS_SELECTOR, ".study-findings.body")
            if findings_div:
                study_caption = findings_div.text.strip()
        except:
            try:
                # Try alternative caption locations
                caption_elements = section.find_elements(By.CSS_SELECTOR, ".sub-section p, .caption")
                if caption_elements:
                    study_caption = caption_elements[0].text.strip()
            except:
                study_caption = "Caption not available"
        
        # Iterate through each series thumbnail
        for series_index, item in enumerate(image_list_items):
            try:
                # Get series name from the caption
                series_name = "Unknown Series"
                try:
                    caption_element = item.find_element(By.CSS_SELECTOR, "._StudyCarouselHeader_ImageListCaption span")
                    series_name = caption_element.get_attribute("title") or caption_element.text.strip()
                    # Clean up series name (remove line breaks, extra spaces)
                    series_name = re.sub(r'\s+', ' ', series_name.replace('\n', ' ')).strip()
                except:
                    series_name = f"Series {series_index + 1}"
                
                print(f"Processing series: {series_name}")
                
                # Click on the series thumbnail to load its images
                try:
                    # Scroll the item into view if needed
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                    time.sleep(0.5)
                    print("passed")
                    
                    # Click on the item
                    ActionChains(driver).move_to_element(item).click().perform()
                    time.sleep(2)  # Wait for images to load
                    print("passed")
                    
                    # Wait for the main image to update
                    time.sleep(5)
                    print("passed")
                    
                except Exception as e:
                    print(f"Warning: Could not click on series {series_index}: {str(e)}")
                    continue
                
                # Now extract the images for this series
                series_images = []
                
                # Method 1: Look for preload links that were loaded after clicking
                try:
                    script = """
                    return Array.from(arguments[0].querySelectorAll('link[rel="preload"][href*="images"]'))
                        .map(link => link.getAttribute('href'));
                    """
                    preload_links = driver.execute_script(script, section)
                    print(f"Found {len(preload_links)} preload links for {series_name}")
                    
                    # Get unique URLs
                    for link in preload_links:
                        if link and link not in series_images:
                            clean_url = link.split('?')[0]
                            series_images.append(clean_url)

                    # Remove any URL with "thumb" in it
                    series_images = [url for url in series_images if "thumb" not in url]
                    
                    print(f"Found {len(series_images)} preload images for {series_name}")
                    
                except Exception as e:
                    print(f"Warning: Could not extract preload links for series {series_index}: {str(e)}")
                
                # Method 2: If no preload links, try to get the currently visible image
                if not series_images:
                    try:
                        main_image = section.find_element(By.CSS_SELECTOR, 'img[src*="dr-original"]')
                        img_src = main_image.get_attribute("src")
                        if img_src and "dr-original" in img_src:
                            clean_url = img_src.split('?')[0]
                            series_images.append(clean_url)
                    except:
                        print(f"Warning: Could not get main image for series {series_index}")
                
                # Method 3: Try to scroll through the series if it's a stack
                if len(series_images) <= 1:
                    try:
                        # Check if this is a stack (has scroll indicator)
                        stack_indicator = item.find_element(By.CSS_SELECTOR, 'img[alt="This study is a stack"]')
                        if stack_indicator:
                            print(f"Series {series_name} is a stack, attempting to extract all images")
                            
                            # Try to get all images in the stack by looking at the network requests
                            # or by finding patterns in the image URLs
                            try:
                                # Get the base URL pattern from the first image
                                if series_images:
                                    base_url = series_images[0]
                                    # Try to find other images with similar patterns
                                    url_pattern = re.sub(r'/(\d+)/', '/{ID}/', base_url)
                                    
                                    # Look for similar URLs in page source or network
                                    script = """
                                    return Array.from(arguments[0].querySelectorAll('link[rel="preload"][href*="images"]'))
                                        .map(link => link.getAttribute('href'));
                                    """
                                    preload_links = driver.execute_script(script, section)
                                    print(len(preload_links))
                                    
                                    # Filter URLs that might belong to this series
                                    if preload_links:
                                        for link in preload_links:
                                            if link and "images" in link and link not in image_data['urls']:
                                                clean_url = link.split('?')[0]
                                                image_data['urls'].append(clean_url)
                            except:
                                pass
                    except:
                        # Not a stack, continue with single image
                        pass
                
                # Store the series data
                if series_images:
                    series_key = f"series_{series_index + 1}_{series_name.replace(' ', '_')}"
                    series_data[series_key] = {
                        'series_name': series_name,
                        'series_index': series_index + 1,
                        'urls': series_images,
                        'caption': study_caption
                    }
                    print(f"Stored {len(series_images)} images for series: {series_name}")
                else:
                    print(f"Warning: No images found for series: {series_name}")
                    
            except Exception as e:
                print(f"Error processing series {series_index}: {str(e)}")
                continue
    
    except Exception as e:
        print(f"Error extracting series from study section: {str(e)}")
        return {}
    
    return series_data

def get_case_data(url, driver):
    """
    Extract case data from a Radiopaedia case page using Selenium
    """
    case_data = {
        'url': url,
        'title': '',
        'modalities': '',
        'patient_age': '',
        'patient_gender': '',
        'presentation': '',
        'case_discussion': '',
        'images': {}
    }
    
    try:
        # Navigate to the case URL
        driver.get(url)
        
        # Wait for the page to fully load by checking for specific elements
        wait = WebDriverWait(driver, 30)
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".case-main-content")))
        except TimeoutException:
            print(f"Warning: Timed out waiting for main content to load on {url}")
        
        # Wait for images to load - check for preload links or image elements
        try:
            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'link[rel="preload"][href*="images"]')) > 0 or 
                               len(d.find_elements(By.CSS_SELECTOR, '.case-section img')) > 0)
        except TimeoutException:
            print(f"Warning: Timed out waiting for images to load on {url}")
        
        # Additional wait for dynamic content to settle
        try:
            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        except:
            print(f"Warning: Document may not be fully loaded on {url}")
        
        # Extract title
        try:
            title_element = driver.find_element(By.CLASS_NAME, "header-title")
            case_data['title'] = title_element.text.strip()
        except NoSuchElementException:
            print(f"Warning: Could not find title for {url}")
        
        # Extract modality
        try:
            modality_elements = driver.find_elements(By.CSS_SELECTOR, ".study-modality .label")
            if modality_elements:
                case_data['modalities'] = [i.text.strip() for i in modality_elements]
        except:
            print(f"Warning: Could not find modality for {url}")
        
        # Extract patient data (age and gender)
        try:
            data_items = driver.find_elements(By.CSS_SELECTOR, ".data-item")
            for item in data_items:
                item_text = item.text.strip()
                if "Age:" in item_text:
                    case_data['patient_age'] = item_text.replace("Age:", "").strip()
                elif "Gender:" in item_text:
                    case_data['patient_gender'] = item_text.replace("Gender:", "").strip()
        except:
            print(f"Warning: Could not find patient data for {url}")

        # Extract presentation
        try:
            data_items = driver.find_elements(By.ID, "case-patient-presentation")
            for item in data_items:
                item_text = item.text.strip()
                if "Presentation" in item_text:
                    case_data['presentation'] = item_text.replace("Presentation", "").strip()
        except:
            print(f"Warning: Could not find patient data for {url}")
        
        # Extract case discussion
        try:
            discussion_element = driver.find_element(By.CSS_SELECTOR, ".case-discussion")
            case_data['case_discussion'] = discussion_element.text.strip()
        except NoSuchElementException:
            # Try alternative method for case discussion
            try:
                discussion_sections = driver.find_elements(By.CSS_SELECTOR, ".case-section")
                for section in discussion_sections:
                    if "Case Discussion" in section.text:
                        case_data['case_discussion'] = section.text.replace("Case Discussion", "").strip()
                        break
            except:
                print(f"Warning: Could not find case discussion for {url}")
        
        # Extract images and captions - UPDATED TO HANDLE MULTIPLE SERIES
        study_group_count = 0
        
        # Look for case-viewer-2022 sections (newer layout)
        study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-viewer-2022")
        
        if not study_sections:
            # Try older layout
            study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-section.case-study")
        
        for i, section in enumerate(study_sections, 1):
            study_group_count += 1
            
            # Try to get study name/title
            study_title = f"Study {i}"
            try:
                study_title_element = section.find_element(By.CSS_SELECTOR, ".study-desc h2")
                study_title = study_title_element.text.strip()
            except:
                pass
            
            print(f"Processing study group: {study_title}")
            
            # Extract all series from this study section
            series_data = extract_series_from_study_section(driver, section, i)
            
            if series_data:
                # Add each series as a separate image group
                for series_key, series_info in series_data.items():
                    group_key = f"study_{study_group_count}_{series_key}"
                    case_data['images'][group_key] = {
                        'study_title': study_title,
                        'series_name': series_info['series_name'],
                        'series_index': series_info['series_index'],
                        'urls': series_info['urls'],
                        'caption': series_info['caption']
                    }
            else:
                # Fallback to original method if series extraction fails
                print(f"Fallback: Using original method for study {i}")
                image_data = {
                    'study_title': study_title,
                    'series_name': 'Main Series',
                    'urls': [],
                    'caption': ''
                }
                
                # Original image extraction logic as fallback
                try:
                    script = """
                    return Array.from(arguments[0].querySelectorAll('link[rel="preload"][href*="images"]'))
                        .map(link => link.getAttribute('href'));
                    """
                    preload_links = driver.execute_script(script, section)
                    
                    if preload_links:
                        for link in preload_links:
                            if link and "images" in link and link not in image_data['urls']:
                                clean_url = link.split('?')[0]
                                image_data['urls'].append(clean_url)
                
                    # Get caption
                    try:
                        findings_div = section.find_element(By.CSS_SELECTOR, ".study-findings.body")
                        if findings_div:
                            image_data['caption'] = findings_div.text.strip()
                    except:
                        image_data['caption'] = 'Caption not available'
                    
                    if image_data['urls']:
                        case_data['images'][f'study_{study_group_count}_main_series'] = image_data
                
                except Exception as e:
                    print(f"Warning: Fallback method failed for section {i}: {str(e)}")
        
        # If we didn't find any images using the above methods, try one more approach
        if not case_data['images']:
            try:
                # Look for any images on the page that might be case images
                all_images = driver.find_elements(By.CSS_SELECTOR, "img[src*='radiopaedia']")
                valid_images = []
                
                for img in all_images:
                    img_src = img.get_attribute("src")
                    if img_src and "spinner" not in img_src and "logo" not in img_src and "icon" not in img_src:
                        valid_images.append(img_src)
                
                if valid_images:
                    case_data['images']['fallback_group'] = {
                        'study_title': 'Case Images',
                        'series_name': 'Main Series',
                        'urls': valid_images,
                        'caption': 'Caption not available'
                    }
            except:
                print(f"Warning: Could not find any images for {url}")
        
        total_series = len(case_data['images'])
        total_images = sum(len(group['urls']) for group in case_data['images'].values())
        print(f"Extracted {total_series} series with {total_images} total images from {url}")
        
        return case_data
        
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return None

import random
def load_case_urls(input_file):
    """
    Load case URLs from a JSON file
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            # INSERT_YOUR_CODE
            data = json.load(f)
            #data = random.sample(data, 200)
            return data
    except Exception as e:
        print(f"Error loading URLs from {input_file}: {e}")
        return []

def load_existing_cases(output_file):
    """
    Load existing cases from the output file
    """
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading existing cases from {output_file}: {e}")
            return []
    return []

def save_cases(cases, output_file):
    """
    Save cases to a JSON file
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(cases)} cases to {output_file}")
    except Exception as e:
        print(f"Error saving cases to {output_file}: {e}")

def process_single_url(url, output_file, lock):
    """
    Process a single URL and return the case data
    """
    driver = get_driver()
    
    try:
        # Get case data
        case_data = get_case_data(url, driver)
        
        if case_data:
            # Acquire lock to safely update the output file
            with lock:
                # Load existing data
                try:
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            all_case_data = json.load(f)
                    else:
                        all_case_data = []
                except:
                    all_case_data = []
                
                # Add new data
                all_case_data.append(case_data)
                
                # Save updated data
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_case_data, f, indent=2, ensure_ascii=False)
            
            return True
        
        return False
    
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return False

def process_case_urls(input_file, output_file, limit=None, max_workers=2):
    """
    Process case URLs in parallel and save the extracted data to a JSON file
    """
    # Load case URLs from the input file
    case_urls = load_case_urls(input_file)
    
    if not case_urls:
        print("No case URLs found. Exiting.")
        return
    
    # Limit the number of URLs to process if specified
    if limit is not None:
        case_urls = case_urls[:limit]
    
    # Filter out URLs that have already been processed
    case_urls = filter_processed_urls(case_urls, output_file)
    
    print(f"Processing {len(case_urls)} case URLs in parallel...")
    
    # Create a lock for thread-safe file operations
    lock = threading.Lock()
    
    # Process URLs in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and track with tqdm for progress bar
        futures = {executor.submit(process_single_url, url, output_file, lock): url for url in case_urls}
        
        # Process results as they complete
        success_count = 0
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Scraping Progress"):
            url = futures[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
    
    # Clean up all drivers
    for thread_id, thread in threading._active.copy().items():
        if hasattr(thread, "driver"):
            try:
                thread.driver.quit()
            except:
                pass
    
    print(f"Successfully processed {success_count} out of {len(case_urls)} cases.")
    print(f"Data saved to {output_file}")

def filter_processed_urls(case_urls, output_file):
    """
    Filter out URLs that have already been processed
    """
    existing_cases = load_existing_cases(output_file)
    existing_urls = [case['url'] for case in existing_cases]
    return [url for url in case_urls if url not in existing_urls]

def main():
    """
    Main function to run the script
    """
    modalities = {
        # "mri": {
        #     "input_file": 'mri_case_urls.json',
        #     "output_file": 'mri_cases_collected.json'
        # },
        # "ct": {
        #     "input_file": 'ct_case_urls.json',
        #     "output_file": 'ct_cases_collected.json'
        # },
        # "x-ray": {
        #     "input_file": 'x-ray_case_urls.json',
        #     "output_file": 'x-ray_cases_collected.json'
        # },
        # "ultrasound": {
        #     "input_file": 'ultrasound_case_urls.json',
        #     "output_file": 'ultrasound_cases_collected.json'
        # },
        "mammography": {
            "input_file": 'mammography_case_urls.json',
            "output_file": 'mammography_cases_collected.json'
        }
    }
    # Select modality
    modality= "mammography"  # Change this to the desired modalityd
    input_file = modalities[modality]["input_file"]
    output_file = modalities[modality]["output_file"]
    if not os.path.exists(input_file):
        print(f"Input file '{input_file}' does not exist. Please run the scraping script first.")
        return
    # Process all URLs with 4 parallel workers (adjust based on your system capabilities)
    max_workers = 2
    limit = 70 # Process all URLs
    
    process_case_urls(input_file, output_file, limit, max_workers)

if __name__ == "__main__":
    main()