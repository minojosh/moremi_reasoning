from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, retry_if_exception_type
import time
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

class Scraper(ABC):
    @abstractmethod
    def fetch_index(self, query, page=1):
        pass

    @abstractmethod
    def parse_index(self, html):
        pass

    @abstractmethod
    def fetch_case(self, url):
        pass

    @abstractmethod
    def extract_case_data(self, html):
        pass

class RadiopaediaScraper(Scraper):
    """
    Scraper for Radiopaedia.org using BeautifulSoup
    """
    BASE_URL = 'https://radiopaedia.org'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://radiopaedia.org/',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    def __init__(self):
        # session with retry/backoff for 429 and server errors
        self.session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    @retry(
        retry=retry_if_exception(lambda e: isinstance(e, HTTPError) and getattr(e.response, 'status_code', None) != 404),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    def fetch_index(self, query, page=1, scope='cases'):
        url = f"{self.BASE_URL}/search?lang=us&page={page}&q={query}&scope={scope}"
        resp = self.session.get(url, headers=self.HEADERS)
        resp.raise_for_status()
        return resp.text

    def parse_index(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.select('a.search-result.search-result-case'):
            href = a.get('href')
            if href:
                if not href.startswith('http'):
                    href = self.BASE_URL + href
                links.append(href)
        return links

    @retry(
        retry=retry_if_exception_type(HTTPError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    def fetch_case(self, url):
        resp = self.session.get(url, headers=self.HEADERS)
        resp.raise_for_status()
        return resp.text

    def extract_case_data(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {
            'case_url': None,
            'image_url': None,
            'diagnosis': None, 
            'presentation': None,
            'age': None,
            'gender': None,
            'findings': None,
            'discussion': None,
            'diagnostic_certainty': None,
            'modality': None,
            'images': []
        }
        
        # title
        title_el = soup.select_one('h1')
        if title_el:
            data['diagnosis'] = title_el.get_text(strip=True)
            
        # modality label
        mod_el = soup.select_one('.study-modality .label')
        if mod_el:
            data['modality'] = mod_el.get_text(strip=True)
            
        # patient info (age, gender) - first try data-item elements
        patient_data = soup.select_one('#case-patient-data')
        if patient_data:
            for div in patient_data.select('div.data-item'):
                label_el = div.select_one('.data-item-label')
                if label_el:
                    label_text = label_el.get_text(strip=True).lower()
                    value_text = div.get_text().replace(label_el.get_text(), '', 1).strip()
                    
                    if 'age' in label_text:
                        data['age'] = value_text
                    elif 'gender' in label_text:
                        data['gender'] = value_text
        
        # If not found in patient-data section, look in other data-items
        if not data['age'] or not data['gender']:
            for div in soup.select('div.data-item'):
                label = div.select_one('.data-item-name, .data-item-label')
                if not label:
                    continue
                
                label_text = label.get_text(strip=True).lower()
                value_text = div.get_text().replace(label.get_text(), '', 1).strip()
                
                if 'age' in label_text and not data['age']:
                    data['age'] = value_text
                elif 'gender' in label_text and not data['gender']:
                    data['gender'] = value_text
                elif 'certainty' in label_text:
                    data['diagnostic_certainty'] = value_text
                    
        # Extract findings from study-findings section
        findings_el = soup.select_one('.study-findings.body')
        if findings_el:
            data['findings'] = findings_el.get_text(strip=True)
        
        # COMPLETELY REDESIGNED IMAGE EXTRACTION STRATEGY
        image_items = []
        logging.info(f"Extracting images from case page")
        
        # 1. Direct pattern matching for Radiopaedia medical images
        # More exact patterns for actual medical images on Radiopaedia
        direct_pattern = re.compile(r'https://prod-images-static\.radiopaedia\.org/images/\d+/[a-f0-9]+\.(jpe?g|png)')
        
        # Search directly in the full HTML for these patterns
        direct_matches = direct_pattern.findall(str(soup))
        for url in direct_matches:
            # Get full-size version (no thumb)
            full_size_url = url.replace("_thumb", "")
            if not any(item['url'] == full_size_url for item in image_items):
                image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                logging.info(f"Found exact pattern match: {full_size_url}")
        
        # 2. Try to get high-quality images from specific image tags
        if not image_items:
            # Find all img tags with sources that contain '/images/' and common image extensions
            for img in soup.find_all('img', src=True):
                src = img['src']
                if '/images/' in src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png']):
                    if any(x in src.lower() for x in ['logo', 'icon', 'spinner', 'loading', 'banner']):
                        continue
                        
                    # Convert to full-size image
                    full_size_url = src.replace("_thumb", "")
                    
                    # Check if the image size is specified in attributes
                    width = img.get('width', '0')
                    height = img.get('height', '0')
                    
                    try:
                        # If dimensions suggest this is a real medical image (not an icon)
                        if int(width) > 100 or int(height) > 100 or (width == '0' and height == '0'):
                            if not any(item['url'] == full_size_url for item in image_items):
                                image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                                logging.info(f"Found img tag with dimensions w:{width} h:{height}: {full_size_url}")
                    except (ValueError, TypeError):
                        # If we can't parse dimensions, still consider the image
                        if not any(item['url'] == full_size_url for item in image_items):
                            image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                            logging.info(f"Found img tag (dimensions unknown): {full_size_url}")
        
        # 3. Look for images within specific containers likely to hold medical images
        if not image_items:
            # Find images within containers that typically hold study images
            study_containers = soup.select('.case-section, .study-section, .study-viewer, .study-browser')
            for container in study_containers:
                for img in container.find_all('img', src=True):
                    src = img['src']
                    if any(x in src.lower() for x in ['logo', 'icon', 'spinner', 'loading', 'banner']):
                        continue
                    
                    if '/images/' in src or 'radiopaedia' in src:
                        full_size_url = src.replace("_thumb", "")
                        if not any(item['url'] == full_size_url for item in image_items):
                            image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                            logging.info(f"Found image in study container: {full_size_url}")
        
        # 4. Look for image URLs in <link> tags (sometimes used for preloading)
        if not image_items:
            for link in soup.find_all('link', attrs={'rel': 'preload', 'as': 'image'}):
                href = link.get('href', '')
                if href and '/images/' in href and not any(x in href.lower() for x in ['logo', 'icon', 'spinner']):
                    full_size_url = href.replace("_thumb", "")
                    if not any(item['url'] == full_size_url for item in image_items):
                        image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                        logging.info(f"Found preloaded image: {full_size_url}")
        
        # 5. Last resort: broader pattern matching
        if not image_items:
            # More permissive pattern to catch other possible image formats
            broader_pattern = re.compile(r'(https://[^"\'\s]+/images/[^"\'\s]+\.(jpe?g|png))')
            broader_matches = broader_pattern.findall(str(soup))
            
            for url_match in broader_matches:
                url = url_match[0]  # Extract the URL from the match tuple
                
                # Skip known UI elements
                if any(x in url.lower() for x in ['logo', 'icon', 'spinner', 'loading', 'alert', 'banner']):
                    continue
                    
                # Get clean URL and convert thumb to full size
                clean_url = url.split('?')[0]
                full_size_url = clean_url.replace("_thumb", "")
                
                if not any(item['url'] == full_size_url for item in image_items):
                    image_items.append({'url': full_size_url, 'annotation': None, 'position': None})
                    logging.info(f"Found broader match: {full_size_url}")
        
        # Extract simple image URLs for backwards compatibility
        data['images'] = [item['url'] for item in image_items if item['url']]
        
        # Add the detailed image objects with annotations
        data['image_details'] = image_items
                
        # Use first image as primary image_url
        if data['images']:
            data['image_url'] = data['images'][0]
            
        # extract text sections
        for section in soup.select('div.case-section'):
            sec_title = section.select_one('h2')
            if sec_title:
                key = sec_title.get_text(strip=True)
                paragraphs = [p.get_text(strip=True) for p in section.select('p') if p.get_text(strip=True)]
                
                if paragraphs:
                    joined_text = ' '.join(paragraphs)
                    
                    # Map section types to output fields
                    key_lower = key.lower()
                    if any(term in key_lower for term in ['presentation', 'clinical']):
                        data['presentation'] = joined_text
                    elif any(term in key_lower for term in ['finding', 'imaging']):
                        data['findings'] = joined_text
                    elif 'discussion' in key_lower:
                        data['discussion'] = joined_text
        
        # If findings not found in sections, look for specific study-findings class
        if not data['findings']:
            findings_div = soup.select_one('.sub-section.study-findings.body')
            if findings_div:
                paragraphs = [p.get_text(strip=True) for p in findings_div.select('p') if p.get_text(strip=True)]
                if paragraphs:
                    data['findings'] = ' '.join(paragraphs)
        
        # If presentation not found in sections, look for specific history class
        if not data['presentation']:
            history_div = soup.select_one('.sub-section.clinical-history.body')
            if history_div:
                paragraphs = [p.get_text(strip=True) for p in history_div.select('p') if p.get_text(strip=True)]
                if paragraphs:
                    data['presentation'] = ' '.join(paragraphs)
        
        # Add fallback for discussion section if missing
        if not data['discussion']:
            discussion_div = soup.select_one('.sub-section.study-discussion.body')
            if discussion_div:
                paras = [p.get_text(strip=True) for p in discussion_div.select('p') if p.get_text(strip=True)]
                if paras:
                    data['discussion'] = ' '.join(paras)
                        
        return data

class SeleniumScraper(RadiopaediaScraper):
    """
    Enhanced Selenium-based scraper designed specifically for image extraction.
    """
    def __init__(self):
        super().__init__()
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run headless Chrome
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")  # Set window size for better rendering
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/113.0.0.0 Safari/537.36")
            self.driver = webdriver.Chrome(service=Service(), options=chrome_options)
            self.driver.implicitly_wait(5)  # Wait up to 5s for elements
            
            # Store references to Selenium classes for later use
            self.By = By
            self.WebDriverWait = WebDriverWait
            self.EC = EC
            
            logging.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Selenium WebDriver: {e}")
            raise
            
    def fetch_case(self, url):
        """Fetch a case page using Selenium for better JavaScript support"""
        logging.info(f"Selenium fetching: {url}")
        self.driver.get(url)
        # Wait for page to fully load
        time.sleep(3)
        return self.driver.page_source
        
    def extract_case_data(self, html):
        """Extract data with enhanced image extraction using Selenium"""
        # Use BeautifulSoup for most data extraction
        data = super().extract_case_data(html)
        
        try:
            # Enhanced image extraction using Selenium
            image_items = []
            
            # Try to find actual medical images using specific selectors
            # Look for images with specific patterns in their src attribute
            img_elements = self.driver.find_elements(self.By.CSS_SELECTOR, 
                'img[src*="images/"][src*=".jpg"], img[src*="images/"][src*=".jpeg"], img[src*="images/"][src*=".png"]')
            
            for img in img_elements:
                try:
                    src = img.get_attribute('src')
                    if not src or any(x in src.lower() for x in ['logo', 'icon', 'spinner', 'loading', 'banner']):
                        continue
                        
                    # Try to get full-size image
                    full_url = src.replace('_thumb', '')
                    
                    # Check image size to filter out UI elements
                    width = img.size['width']
                    height = img.size['height']
                    
                    # Only include reasonably sized images (likely medical images)
                    if width > 100 and height > 100:
                        if not any(item['url'] == full_url for item in image_items):
                            image_items.append({'url': full_url, 'annotation': None, 'position': None})
                            logging.info(f"Found image via Selenium: {full_url} ({width}x{height})")
                except Exception as e:
                    logging.warning(f"Error processing image element: {e}")
            
            # If we found images, update the data
            if image_items:
                data['images'] = [item['url'] for item in image_items]
                data['image_details'] = image_items
                if data['images']:
                    data['image_url'] = data['images'][0]
                    
        except Exception as e:
            logging.error(f"Error during Selenium image extraction: {e}")
            
        return data
        
    def __del__(self):
        """Clean up Selenium WebDriver when object is destroyed"""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except Exception as e:
                logging.warning(f"Error closing Selenium WebDriver: {e}")