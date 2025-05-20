from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, retry_if_exception_type
import time

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
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'text/html',
        'Accept-Language': 'en-US'
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
        
        # Image extraction - check for study carousel first (preferred)
        image_items = []
        
        # Look for modern carousel structure with list box containers
        box_items = soup.select('div._StudyCarouselHeader_ImageListBox')
        if box_items:
            for box in box_items:
                img_data = {'url': None, 'annotation': None, 'position': None}

                # Extract image URL: prefer <link rel="preload" as="image"> over <img>
                link_tag = box.find('link', attrs={'rel':'preload','as':'image'})
                if link_tag and link_tag.has_attr('href'):
                    src = link_tag['href']
                else:
                    img_tag = box.find('img')
                    src = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
                if src and 'spinner' not in src and 'data:image' not in src:
                    clean = src.split('?')[0]
                    img_data['url'] = clean.replace('_thumb','_gallery') if '_thumb' in clean else clean

                # Extract caption from adjacent caption container
                caption_div = box.find_next_sibling('div', class_='_StudyCarouselHeader_ImageListCaption')
                if caption_div:
                    span = caption_div.find('span')
                    if span:
                        img_data['annotation'] = span.get_text(strip=True)

                if img_data['url']:
                    image_items.append(img_data)
        else:
            # Fallback to modern carousel structure with annotations
            carousel_items = soup.select('._StudyCarouselHeader_ImageListItem')
            if carousel_items:
                for item in carousel_items:
                    img_data = {'url': None, 'annotation': None, 'position': None}
                    # Extract image URL
                    img_tag = item.select_one('img')
                    if img_tag and img_tag.has_attr('src'):
                        src = img_tag['src']
                        if 'spinner' not in src and 'data:image' not in src:
                            img_data['url'] = src.split('?')[0]
                            # Try to get higher quality version by replacing _thumb with _gallery
                            if '_thumb' in img_data['url']:
                                img_data['url'] = img_data['url'].replace('_thumb', '_gallery')

                    # Extract position/annotation from caption
                    caption = item.select_one('._StudyCarouselHeader_ImageListCaption')
                    if caption:
                        # Prefer title attribute
                        annotation_spans = caption.select('span[title]')
                        if annotation_spans:
                            img_data['annotation'] = annotation_spans[0].get('title', '')
                        else:
                            annotation_text = caption.get_text(strip=True)
                            if annotation_text:
                                img_data['annotation'] = annotation_text

                    if img_data['url']:
                        image_items.append(img_data)
                
                # Get position attribute if available
                if item.has_attr('data-sortable-id'):
                    img_data['position'] = item['data-sortable-id']
                
                if img_data['url']:
                    image_items.append(img_data)
        
        # BS4 fallback: collect preload links inside carousel container
        if not image_items:
            container = soup.select_one('div._StudyCarouselHeader_Container')
            if container:
                for link in container.select('link[rel="preload"][as="image"]'):
                    href = link.get('href')
                    if href and 'spinner' not in href and 'data:image' not in href:
                        clean_url = href.split('?')[0]
                        image_items.append({'url': clean_url, 'annotation': None, 'position': str(len(image_items))})
        
        # Fallback: collect preload links anywhere
        if not image_items:
            for link in soup.select('link[rel="preload"][as="image"]'):
                href = link.get('href')
                if href and 'data:image' not in href and 'spinner' not in href:
                    clean_url = href.split('?')[0]
                    if not any(item['url'] == clean_url for item in image_items):
                        image_items.append({'url': clean_url, 'annotation': None, 'position': str(len(image_items))})
        
        # Fall back to standard image extraction if carousel not found
        if not image_items:
            # image URLs from img tags in case sections
            for img in soup.select('.case-section img'):
                src = img.get('src') or img.get('data-src')  # Try data-src if src is not available
                if src and 'data:image' not in src and 'spinner' not in src:
                    clean_url = src.split('?')[0]
                    image_items.append({'url': clean_url, 'annotation': None, 'position': None})
                
            # Also check for hidden high-res images sometimes available in data attributes
            for img in soup.select('.case-section img[data-full-res]'):
                src = img.get('data-full-res')
                if src and 'data:image' not in src and 'spinner' not in src:
                    clean_url = src.split('?')[0]
                    if not any(item['url'] == clean_url for item in image_items):
                        image_items.append({'url': clean_url, 'annotation': None, 'position': None})
        
        # Ultimate fallback: any <img> across the page
        if not image_items:
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src:
                    continue
                if 'data:image' in src or 'spinner' in src:
                    continue
                clean_url = src.split('?')[0]
                if not any(item['url'] == clean_url for item in image_items):
                    image_items.append({'url': clean_url, 'annotation': None, 'position': None})
        
        # Sort by position if available
        if any(item['position'] is not None for item in image_items):
            image_items.sort(key=lambda x: int(x['position']) if x['position'] is not None else 999)
        
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
    Selenium-based scraper fallback for dynamic content.
    """
    def __init__(self):
        super().__init__()
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run headless Chrome
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(service=Service(), options=chrome_options)