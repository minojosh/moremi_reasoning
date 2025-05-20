import os
import time
import json
import logging
import argparse

from requests.exceptions import HTTPError
from tenacity import RetryError
from src.utils.config import load_config
from radiopedia_data.scraper import RadiopaediaScraper, SeleniumScraper
from selenium.common.exceptions import WebDriverException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def main():
    # parse command-line arguments
    parser = argparse.ArgumentParser(description='Radiopaedia scraper')
    parser.add_argument('--backend', choices=['bs4', 'selenium'], default='bs4', help='Scraper backend to use')
    parser.add_argument('--max-cases', type=int, default=None, help='Maximum number of cases to scrape per modality')
    args = parser.parse_args()

    # Load modalities config
    modalities = load_config()
    if not modalities:
        logging.error("No modalities found in config.")
        return

    # instantiate scraper based on backend
    if args.backend == 'selenium':
        logging.info('Attempting SeleniumScraper backend')
        try:
            scraper = SeleniumScraper()
            logging.info('SeleniumScraper initialized successfully')
        except WebDriverException as e:
            logging.warning(f"SeleniumScraper init failed (status {e}); falling back to BS4: {e}")
            scraper = RadiopaediaScraper()
    else:
        logging.info('Using RadiopaediaScraper (BS4) backend')
        scraper = RadiopaediaScraper()

    out_dir = os.path.dirname(__file__)
    os.makedirs(out_dir, exist_ok=True)

    for modality, cfg in modalities.items():
        keywords = cfg.get('keywords', [])
        logging.info(f"Starting scrape for modality '{modality}' with keywords {keywords}")

        # collect case URLs
        case_urls = set()
        for keyword in keywords:
            page = 1
            while True:
                logging.info(f"Fetching index for '{keyword}', page {page}")
                try:
                    html = scraper.fetch_index(keyword, page)
                except RetryError as re:
                    cause = re.last_attempt.exception()
                    if isinstance(cause, HTTPError) and cause.response.status_code == 404:
                        logging.info(f"No more index pages for '{keyword}' at page {page} (404).")
                        break
                    else:
                        raise re
                except HTTPError as e:
                    if e.response.status_code == 404:
                        logging.info(f"No more index pages for '{keyword}' at page {page} (404).")
                        break
                    else:
                        raise
                links = scraper.parse_index(html)
                if not links:
                    break
                new_links = [u for u in links if u not in case_urls]
                if not new_links:
                    break
                case_urls.update(new_links)
                page += 1
                time.sleep(1)

        logging.info(f"Found {len(case_urls)} total case URLs for '{modality}'")
        # apply max-cases limit
        if args.max_cases is not None:
            original = len(case_urls)
            case_list = list(case_urls)[:args.max_cases]
            case_urls = case_list
            logging.info(f"Limiting to first {len(case_urls)} cases (from {original}) for '{modality}'")
        else:
            case_list = list(case_urls)

        # fetch case data and filter by modality label
        cases = []
        for url in case_list:
            try:
                html = scraper.fetch_case(url)
                data = scraper.extract_case_data(html)
                data['case_url'] = url
                if data.get('modality', '').lower() == modality.lower():
                    cases.append(data)
            except Exception as e:
                logging.warning(f"Failed extracting case data from {url}: {e}")

        # save cases data
        out_file = os.path.join(out_dir, f"{modality}_cases.json")
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(cases)} cases to {out_file}")


if __name__ == '__main__':
    main()