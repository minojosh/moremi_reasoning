import json
import time
import threading
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from tqdm import tqdm
from typing import Dict, List, Optional
import sys
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import urllib3.exceptions
import socket

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.config_loader import load_radiopedia_config
from utils.path_config import get_radiopedia_data_path
from utils.logger import setup_logger

logger = setup_logger('case_scraper')
thread_local = threading.local()


class RadiopaediaCaseScraper:
    """Scraper for extracting detailed case data from Radiopaedia."""
    
    def __init__(self, run_path=None):
        self.config = load_radiopedia_config()
        self.max_workers = self.config['default']['max_workers']
        self.timeout = self.config['default']['timeout']
        self.run_path = run_path or get_radiopedia_data_path()  # Use timestamped path if provided
    
    def setup_driver(self) -> webdriver.Chrome:
        """Set up Chrome WebDriver with optimized options."""
        chrome_options = Options()
        for option in self.config['selenium']['chrome_options']:
            chrome_options.add_argument(option)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow', 
            'downloadPath': str(self.run_path)
        })
        return driver
    
    def get_driver(self) -> webdriver.Chrome:
        """Get thread-local WebDriver instance."""
        if not hasattr(thread_local, "driver"):
            thread_local.driver = self.setup_driver()
        return thread_local.driver
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((
            TimeoutException, 
            WebDriverException, 
            urllib3.exceptions.HTTPError,
            urllib3.exceptions.TimeoutError,
            urllib3.exceptions.ReadTimeoutError,
            socket.timeout,
            OSError,
            ConnectionError
        )),
        reraise=True
    )
    def extract_case_data(self, url: str, driver: webdriver.Chrome) -> Optional[Dict]:
        """Extract comprehensive case data from a Radiopaedia case page with retry logic."""
        case_data = {
            'url': url,
            'title': '',
            'modalities': [],
            'patient_age': '',
            'patient_gender': '',
            'presentation': '',
            'case_discussion': '',
            'images': {}
        }
        
        try:
            logger.info(f"Attempting to extract data from: {url}")
            driver.get(url)
            wait = WebDriverWait(driver, self.timeout)
            
            # Wait for main content
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".case-main-content")))
            except TimeoutException:
                logger.warning(f"Timeout waiting for main content: {url}")
                raise  # Re-raise to trigger retry
            
            # Extract title
            try:
                title_element = driver.find_element(By.CLASS_NAME, "header-title")
                case_data['title'] = title_element.text.strip()
            except NoSuchElementException:
                logger.warning(f"No title found: {url}")
            
            # Extract modality
            try:
                modality_elements = driver.find_elements(By.CSS_SELECTOR, ".study-modality .label")
                case_data['modalities'] = [elem.text.strip() for elem in modality_elements]
            except:
                logger.warning(f"No modality found: {url}")
            
            # Extract patient data
            try:
                data_items = driver.find_elements(By.CSS_SELECTOR, ".data-item")
                for item in data_items:
                    item_text = item.text.strip()
                    if "Age:" in item_text:
                        case_data['patient_age'] = item_text.replace("Age:", "").strip()
                    elif "Gender:" in item_text:
                        case_data['patient_gender'] = item_text.replace("Gender:", "").strip()
            except:
                logger.warning(f"No patient data found: {url}")
            
            # Extract presentation
            try:
                presentation_items = driver.find_elements(By.ID, "case-patient-presentation")
                for item in presentation_items:
                    case_data['presentation'] = item.text.strip()
            except:
                logger.warning(f"No presentation found: {url}")
            
            # Extract case discussion
            try:
                discussion_element = driver.find_element(By.CSS_SELECTOR, ".case-discussion")
                case_data['case_discussion'] = discussion_element.text.strip()
            except NoSuchElementException:
                try:
                    discussion_sections = driver.find_elements(By.CSS_SELECTOR, ".case-section")
                    for section in discussion_sections:
                        if "discussion" in section.text.lower():
                            case_data['case_discussion'] = section.text.strip()
                            break
                except:
                    logger.warning(f"No case discussion found: {url}")
            
            # Extract images - simplified approach for now
            self._extract_images(driver, case_data)
            
            total_images = sum(len(group.get('urls', [])) for group in case_data['images'].values())
            logger.info(f"Successfully extracted {len(case_data['images'])} series with {total_images} images from {url}")
            
            return case_data
            
        except (
            TimeoutException, 
            WebDriverException, 
            urllib3.exceptions.HTTPError,
            urllib3.exceptions.TimeoutError,
            urllib3.exceptions.ReadTimeoutError,
            socket.timeout,
            OSError,
            ConnectionError
        ) as e:
            logger.warning(f"Retryable error processing {url}: {str(e)}")
            raise  # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Non-retryable error processing {url}: {str(e)}")
            return None
    
    def _extract_images(self, driver: webdriver.Chrome, case_data: Dict):
        """Extract image data from case page."""
        study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-viewer-2022")
        if not study_sections:
            study_sections = driver.find_elements(By.CSS_SELECTOR, ".case-section.case-study")
        
        for i, section in enumerate(study_sections, 1):
            study_title = f"Study {i}"
            try:
                study_title_element = section.find_element(By.CSS_SELECTOR, ".study-desc h2")
                study_title = study_title_element.text.strip()
            except:
                pass
            
            # Get study caption
            study_caption = ""
            try:
                findings_div = section.find_element(By.CSS_SELECTOR, ".study-findings.body")
                study_caption = findings_div.text.strip()
            except:
                try:
                    caption_elements = section.find_elements(By.CSS_SELECTOR, ".sub-section p, .caption")
                    if caption_elements:
                        study_caption = caption_elements[0].text.strip()
                except:
                    study_caption = "Caption not available"
            
            # Extract image URLs (simplified)
            image_urls = []
            try:
                img_elements = section.find_elements(By.CSS_SELECTOR, "img[src*='radiopaedia']")
                for img in img_elements:
                    src = img.get_attribute('src')
                    if src and 'images' in src:
                        image_urls.append(src)
            except:
                pass
            
            if image_urls:
                case_data['images'][f"series_{i}"] = {
                    'study_title': study_title,
                    'series_name': 'Main Series',
                    'urls': image_urls,
                    'caption': study_caption
                }
    
    def load_case_urls(self, modality: str) -> List[str]:
        """Load case URLs from file."""
        url_filename = f"{modality}{self.config['output']['url_file_suffix']}"
        urls_dir = self.run_path / self.config['output']['directories']['scraped_urls']
        filepath = urls_dir / url_filename
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading URLs from {filepath}: {e}")
            return []
    
    def load_existing_cases(self, modality: str) -> List[Dict]:
        """Load existing cases from output file."""
        cases_filename = f"{modality}{self.config['output']['cases_file_suffix']}"
        cases_dir = self.run_path / self.config['output']['directories']['scraped_cases']
        filepath = cases_dir / cases_filename
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing cases: {e}")
                return []
        return []
    
    def save_cases(self, cases: List[Dict], modality: str):
        """Save cases to JSON file."""
        cases_filename = f"{modality}{self.config['output']['cases_file_suffix']}"
        cases_dir = self.run_path / self.config['output']['directories']['scraped_cases']
        cases_dir.mkdir(exist_ok=True)
        filepath = cases_dir / cases_filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cases, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(cases)} cases to {filepath}")
        except Exception as e:
            logger.error(f"Error saving cases: {e}")
    
    def process_single_url(self, url: str, output_file: str, lock: threading.Lock) -> bool:
        """Process a single URL and save the case data."""
        driver = self.get_driver()
        
        try:
            case_data = self.extract_case_data(url, driver)
            
            if case_data:
                with lock:
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            all_case_data = json.load(f)
                    except:
                        all_case_data = []
                    
                    all_case_data.append(case_data)
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(all_case_data, f, indent=2, ensure_ascii=False)
                
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            return False
    
    def scrape_modality_cases(self, modality: str, limit: int = 50) -> int:
        """Scrape case data for a specific modality."""
        case_urls = self.load_case_urls(modality)
        if not case_urls:
            logger.warning(f"No URLs found for modality: {modality}")
            return 0
        
        # Limit URLs to process
        case_urls = case_urls[:limit]
        
        # Filter out already processed URLs
        existing_cases = self.load_existing_cases(modality)
        existing_urls = {case['url'] for case in existing_cases}
        case_urls = [url for url in case_urls if url not in existing_urls]
        
        if not case_urls:
            logger.info(f"All URLs for {modality} already processed")
            return len(existing_cases)
        
        logger.info(f"Processing {len(case_urls)} new URLs for {modality}")
        
        cases_filename = f"{modality}{self.config['output']['cases_file_suffix']}"
        cases_dir = self.run_path / self.config['output']['directories']['scraped_cases']
        cases_dir.mkdir(exist_ok=True)
        output_file = cases_dir / cases_filename
        
        lock = threading.Lock()
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_single_url, url, output_file, lock): url 
                for url in case_urls
            }
            
            for future in tqdm(concurrent.futures.as_completed(futures), 
                             total=len(futures), desc=f"Scraping {modality}"):
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Future error: {str(e)}")
        
        # Cleanup drivers
        for thread_id, thread in threading._active.copy().items():
            if hasattr(thread, "driver"):
                try:
                    thread.driver.quit()
                except:
                    pass
        
        total_cases = len(existing_cases) + success_count
        logger.info(f"Successfully processed {success_count} new cases for {modality}")
        logger.info(f"Total cases for {modality}: {total_cases}")
        
        return total_cases
