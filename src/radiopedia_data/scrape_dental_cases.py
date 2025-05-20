import json
import time
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
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
    
    # Create a new Chrome WebDriver instance using webdriver-manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Set page load strategy to 'eager' - wait only until DOM is ready
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': os.getcwd()})
    
    return driver

def get_case_data(url, driver):
    """
    Extract case data from a Radiopaedia case page using Selenium
    """
    case_data = {
        'url': url,
        'title': '',
        'modality': '',
        'patient_age': '',
        'patient_gender': '',
        'case_discussion': '',
        'images': {}
    }
    
    try:
        # Navigate to the case URL
        driver.get(url)
        
        # Wait for the page to fully load by checking for specific elements
        wait = WebDriverWait(driver, 30)
        
        # Wait for the main content to load
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".case-main-content")))
        except TimeoutException:
            print(f"Warning: Timed out waiting for main content to load on {url}")
        
        # Wait for images to load - check for preload links or image elements
        try:
            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'link[rel="preload"][href*="images"]')) > 0 or len(d.find_elements(By.CSS_SELECTOR, '.case-section img')) > 0)
        except TimeoutException:
            print(f"Warning: Timed out waiting for images to load on {url}")
        
        # Additional wait for dynamic content to settle
        try:
            # Wait for network activity to settle (check if document.readyState is complete)
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
                case_data['modality'] = modality_elements[0].text.strip()
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
        
        # Extract images and captions
        image_group_count = 0
        
        # Look for case-viewer-2022 sections (newer layout)
        study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-viewer-2022")
        
        if not study_sections:
            # Try older layout
            study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-section.case-study")
        
        for i, section in enumerate(study_sections, 1):
            image_group_count += 1
            image_data = {
                'urls': [],
                'caption': ''
            }
            
            # Try to get study name/title
            try:
                study_title = section.find_element(By.CSS_SELECTOR, ".study-desc h2").text.strip()
                image_data['title'] = study_title
            except:
                image_data['title'] = f"Study {i}"
            
            # Try to get image URLs - SPECIFICALLY TARGETING PRELOAD LINKS
            try:
                # Look for preload links which contain the actual image URLs
                script = """
                return Array.from(arguments[0].querySelectorAll('link[rel="preload"][href*="images"]'))
                    .map(link => link.getAttribute('href'));
                """
                preload_links = driver.execute_script(script, section)
                
                if preload_links:
                    for link in preload_links:
                        if link and "images" in link and link not in image_data['urls']:
                            # Clean up URL (remove any query parameters)
                            clean_url = link.split('?')[0]
                            image_data['urls'].append(clean_url)
                
                # If no preload links found, try regular images
                if not image_data['urls']:
                    images = section.find_elements(By.CSS_SELECTOR, "img")
                    for img in images:
                        try:
                            img_src = img.get_attribute("src")
                            if img_src and "spinner" not in img_src and "data:image" not in img_src:
                                image_data['urls'].append(img_src)
                        except:
                            continue
                
                # If still no images found, try to find them in other ways
                if not image_data['urls']:
                    # Try to find image in background style
                    elements_with_bg = section.find_elements(By.CSS_SELECTOR, "[style*='background-image']")
                    for elem in elements_with_bg:
                        style = elem.get_attribute("style")
                        if style and "url(" in style:
                            url_match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                            if url_match:
                                image_data['urls'].append(url_match.group(1))
            except Exception as e:
                print(f"Warning: Could not extract images from section {i}: {str(e)}")
            
            # Try to get caption
            try:
                findings_div = section.find_element(By.CSS_SELECTOR, ".study-findings.body")
                if findings_div:
                    image_data['caption'] = findings_div.text.strip()
            except:
                try:
                    # Try alternative caption locations
                    caption_elements = section.find_elements(By.CSS_SELECTOR, ".sub-section p, .caption")
                    if caption_elements:
                        image_data['caption'] = caption_elements[0].text.strip()
                except:
                    print(f"Warning: Could not find caption for section {i}")
            
            # Add image data to case data if we found any URLs
            if image_data['urls']:
                case_data['images'][f'group_{image_group_count}'] = image_data
        
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
                    case_data['images']['group_1'] = {
                        'title': 'Case Images',
                        'urls': valid_images,
                        'caption': 'Caption not available'
                    }
            except:
                print(f"Warning: Could not find any images for {url}")
        
        print(f"Extracted {len(case_data['images'])} image groups from {url}")
        return case_data
        
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return None

def load_case_urls(input_file):
    """
    Load case URLs from a JSON file
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)[264:]
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
    input_file = 'mammogram_case_urls.json'
    output_file = 'mammogram_case_collected.json'
    
    # Process all URLs with 4 parallel workers (adjust based on your system capabilities)
    max_workers = 2
    limit = None  # Process all URLs
    
    process_case_urls(input_file, output_file, limit, max_workers)

if __name__ == "__main__":
    main()
