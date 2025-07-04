import requests
import time
import json
import os
from bs4 import BeautifulSoup
from typing import List, Set
import sys
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException, Timeout, ConnectionError

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.config_loader import load_radiopedia_config, get_modality_keywords
from utils.path_config import get_radiopedia_data_path
from utils.logger import setup_logger

logger = setup_logger('url_scraper')


class RadiopaediaURLScraper:
    """Scraper for collecting Radiopaedia case URLs by modality."""
    
    def __init__(self, run_path=None):
        self.config = load_radiopedia_config()
        self.base_url = self.config['scraping']['base_url']
        self.headers = self.config['scraping']['headers']
        self.delay = self.config['default']['delay_between_requests']
        self.run_path = run_path or get_radiopedia_data_path()  # Use timestamped path if provided
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((RequestException, Timeout, ConnectionError)),
        reraise=True
    )
    def scrape_search_page(self, query: str, page: int = 1) -> BeautifulSoup:
        """Scrape a single search results page with retry logic."""
        url = f"{self.base_url}?lang=us&page={page}&q={query}&scope=cases"
        logger.info(f"Scraping: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            else:
                logger.error(f"HTTP {response.status_code} for {url}")
                raise RequestException(f"HTTP {response.status_code}")
        except (RequestException, Timeout, ConnectionError) as e:
            logger.warning(f"Retryable error scraping {url}: {str(e)}")
            raise  # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Non-retryable error scraping {url}: {str(e)}")
            return None
    
    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total number of pages from pagination."""
        pagination_links = soup.select('div[role="navigation"][class*="pagination"] a[aria-label^="Page"]')
        
        if not pagination_links:
            return 1
        
        page_numbers = []
        for link in pagination_links:
            aria_label = link.get('aria-label', '')
            if aria_label.startswith('Page '):
                try:
                    page_number = int(aria_label.replace('Page ', '').strip())
                    page_numbers.append(page_number)
                except ValueError:
                    continue
        
        return max(page_numbers) if page_numbers else 1
    
    def extract_case_urls(self, soup: BeautifulSoup) -> List[str]:
        """Extract case URLs from search results."""
        case_urls = []
        case_elements = soup.select('a.search-result.search-result-case')
        
        for case in case_elements:
            if case and 'href' in case.attrs:
                case_url = case['href']
                if not case_url.startswith('http'):
                    case_url = 'https://radiopaedia.org' + case_url
                case_urls.append(case_url)
        
        return case_urls
    
    def load_existing_urls(self, filename: str) -> Set[str]:
        """Load existing URLs from file."""
        urls_dir = self.run_path / self.config['output']['directories']['scraped_urls']
        urls_dir.mkdir(exist_ok=True)
        filepath = urls_dir / filename
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_urls(self, urls: Set[str], filename: str):
        """Save URLs to JSON file."""
        urls_dir = self.run_path / self.config['output']['directories']['scraped_urls']
        urls_dir.mkdir(exist_ok=True)
        filepath = urls_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(urls), f, indent=4, ensure_ascii=False)
        logger.info(f"Saved {len(urls)} URLs to {filepath}")
    
    def scrape_modality_urls(self, modality: str, limit: int = 50) -> Set[str]:
        """Scrape URLs for a specific modality with limit."""
        keywords = get_modality_keywords(modality)
        if not keywords:
            logger.warning(f"No keywords found for modality: {modality}")
            return set()
        
        url_filename = f"{modality}{self.config['output']['url_file_suffix']}"
        all_urls = self.load_existing_urls(url_filename)
        initial_count = len(all_urls)
        
        logger.info(f"Processing modality: {modality}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Loaded {initial_count} existing URLs")
        
        for keyword in keywords:
            if len(all_urls) >= limit:
                logger.info(f"Reached limit of {limit} URLs")
                break
                
            logger.info(f"Searching for keyword: {keyword}")
            
            # Get first page to determine total pages
            soup = self.scrape_search_page(keyword, 1)
            if not soup:
                continue
            
            total_pages = self.get_total_pages(soup)
            logger.info(f"Found {total_pages} pages for '{keyword}'")
            
            # Process pages until we reach the limit
            for page in range(1, total_pages + 1):
                if len(all_urls) >= limit:
                    break
                    
                if page > 1:
                    soup = self.scrape_search_page(keyword, page)
                    if not soup:
                        continue
                
                urls = self.extract_case_urls(soup)
                new_urls = [url for url in urls if url not in all_urls]
                all_urls.update(new_urls[:limit - len(all_urls)])
                
                logger.info(f"Page {page}: Found {len(new_urls)} new URLs")
                
                if page < total_pages:
                    time.sleep(self.delay)
        
        self.save_urls(all_urls, url_filename)
        logger.info(f"Total URLs for {modality}: {len(all_urls)}")
        logger.info(f"New URLs added: {len(all_urls) - initial_count}")
        
        return all_urls
