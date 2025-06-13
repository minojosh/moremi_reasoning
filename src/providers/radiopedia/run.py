import os
import time
import json
import logging
import argparse
import sys
import yaml
from tqdm import tqdm

from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
from tenacity import RetryError
from selenium.common.exceptions import WebDriverException

# Local imports - using relative paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../'))
sys.path.insert(0, project_root)

# Import scraper from the current directory
from src.providers.radiopedia.scraper import RadiopaediaScraper, SeleniumScraper

# Define a local load_config function to avoid import issues
def load_config(path=os.path.join(project_root, "src/config/modalities.yaml")):
    """
    Load modalities configuration from YAML file.
    Returns a dict mapping modality names to their config.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        return cfg.get('modalities', {})
    except FileNotFoundError:
        logging.error(f"Config file not found: {path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML config: {e}")
        return {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def main():
    # parse command-line arguments
    parser = argparse.ArgumentParser(description='Radiopaedia scraper')
    parser.add_argument('--backend', choices=['bs4', 'selenium'], default='selenium', help='Scraper backend to use')
    parser.add_argument('--max-cases', type=int, default=100, help='Maximum number of cases to scrape per modality')
    parser.add_argument('--max-urls-per-keyword', type=int, default=None, 
                        help='Maximum number of case URLs to collect per keyword')
    parser.add_argument('--output-dir', type=str, default=os.path.join(project_root, "src/data/radiopedia"),
                        help='Directory to save output files (default: script directory)')
    parser.add_argument('--validate-images', action='store_true', help='Validate that images are medical images')
    parser.add_argument('--modalities', type=str, default='all', 
                        help='Comma-separated list of modalities to process, or "all" for every modality in modalities.yaml (default: all)')
    args = parser.parse_args()

    # Load modalities config
    all_modalities_config = load_config()
    if not all_modalities_config:
        logging.error("No modalities found in config.")
        return

    selected_modalities_names = []
    if args.modalities.lower() == 'all':
        selected_modalities_names = list(all_modalities_config.keys())
    else:
        selected_modalities_names = [m.strip() for m in args.modalities.split(',') if m.strip() in all_modalities_config]
        if not selected_modalities_names:
            logging.error(f"No valid modalities selected from: {args.modalities}. Available: {list(all_modalities_config.keys())}")
            return
        # Log if some requested modalities were not found
        requested_modalities = [m.strip() for m in args.modalities.split(',')]
        not_found_modalities = [m for m in requested_modalities if m not in all_modalities_config]
        if not_found_modalities:
            logging.warning(f"The following requested modalities were not found in modalities.yaml and will be skipped: {', '.join(not_found_modalities)}")
    
    # instantiate scraper based on backend with Selenium as default for better image extraction
    if args.backend == 'selenium':
        logging.info('Attempting SeleniumScraper backend (recommended for image extraction)')
        try:
            scraper = SeleniumScraper()
            logging.info('SeleniumScraper initialized successfully')
        except Exception as e:
            logging.warning(f"SeleniumScraper init failed ({type(e).__name__}: {e}); falling back to BS4")
            scraper = RadiopaediaScraper()
    else:
        logging.info('Using RadiopaediaScraper (BS4) backend - note that image extraction may be less reliable')
        scraper = RadiopaediaScraper()

    # Set output directory
    out_dir = args.output_dir if args.output_dir else os.path.dirname(__file__)
    os.makedirs(out_dir, exist_ok=True)

    for modality_name in selected_modalities_names:
        cfg = all_modalities_config[modality_name]
        keywords = cfg.get('keywords', [])
        logging.info(f"Starting scrape for modality '{modality_name}' with keywords {keywords}")

        # collect case URLs
        case_urls = set()
        for keyword in keywords:
            page = 1
            urls_for_keyword = 0
            while True:
                if args.max_urls_per_keyword and urls_for_keyword >= args.max_urls_per_keyword:
                    logging.info(f"Reached max URLs limit ({args.max_urls_per_keyword}) for keyword '{keyword}'")
                    break
                    
                logging.info(f"Fetching index for '{keyword}', page {page}")
                try:
                    html = scraper.fetch_index(keyword, page)
                except RetryError as re:
                    cause = re.last_attempt.exception()
                    if isinstance(cause, HTTPError) and cause.response.status_code == 404:
                        logging.info(f"No more index pages for '{keyword}' at page {page} (404).")
                        break
                    else:
                        logging.warning(f"Error fetching index for '{keyword}' page {page}: {re}")
                        break
                except (HTTPError, ConnectionError, Timeout, RequestException) as e:
                    if isinstance(e, HTTPError) and e.response.status_code == 404:
                        logging.info(f"No more index pages for '{keyword}' at page {page} (404).")
                        break
                    logging.warning(f"Error fetching index for '{keyword}' page {page}: {e}")
                    break
                except Exception as e:
                    logging.error(f"Unexpected error fetching index for '{keyword}' page {page}: {e}")
                    break
                    
                links = scraper.parse_index(html)
                if not links:
                    break
                    
                new_links = [u for u in links if u not in case_urls]
                if not new_links:
                    break
                    
                case_urls.update(new_links)
                urls_for_keyword += len(new_links)
                page += 1
                time.sleep(1)

        logging.info(f"Found {len(case_urls)} total case URLs for '{modality_name}'")
        
        # apply max-cases limit
        if args.max_cases is not None:
            original = len(case_urls)
            case_list = list(case_urls)[:args.max_cases]
            case_urls = case_list
            logging.info(f"Limiting to first {len(case_urls)} cases (from {original}) for '{modality_name}'")
        else:
            case_list = list(case_urls)

        # fetch case data and filter by modality label
        cases = []
        case_pbar = tqdm(case_list, desc=f"Fetching cases for '{modality_name}'", unit="case")
        
        for url in case_pbar:
            case_pbar.set_description(f"Fetching {url.split('/')[-1]}")
            try:
                html = scraper.fetch_case(url)
                data = scraper.extract_case_data(html)
                data['case_url'] = url
                if data.get('modality', '').lower() == modality_name.lower():
                    cases.append(data)
                    case_pbar.set_postfix({"collected": len(cases)})
                else:
                    logging.debug(f"Skipping case {url} with modality '{data.get('modality', 'unknown')}'")
            except KeyboardInterrupt:
                logging.info("Process interrupted by user. Saving collected data so far...")
                break
            except Exception as e:
                logging.warning(f"Failed extracting case data from {url}: {e}")
            
            # Add a small delay to be nice to the server
            time.sleep(0.5)

        # save cases data (even if interrupted)
        if cases:
            # Validate images if requested
            if args.validate_images:
                validated_cases = []
                validation_pbar = tqdm(cases, desc="Validating images", unit="case")
                
                for case in validation_pbar:
                    # Filter out known non-medical image patterns
                    filtered_images = []
                    filtered_details = []
                    
                    if case['images']:
                        for i, img_url in enumerate(case['images']):
                            # Skip images that match common non-medical patterns
                            if any(x in img_url.lower() for x in [
                                'logo', 'banner', 'promotional', 'icon', 'spinner', 
                                'loading', 'error', 'alert', '/assets/'
                            ]):
                                logging.debug(f"Skipping non-medical image: {img_url}")
                                continue
                                
                            # Only keep images that appear to be from the image repository
                            if '/images/' in img_url and any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png']):
                                filtered_images.append(img_url)
                                if i < len(case['image_details']):
                                    filtered_details.append(case['image_details'][i])
                    
                    # Update the case with filtered images
                    if filtered_images:
                        case['images'] = filtered_images
                        case['image_details'] = filtered_details
                        case['image_url'] = filtered_images[0] if filtered_images else None
                        validated_cases.append(case)
                    else:
                        logging.warning(f"Case {case.get('diagnosis', 'unknown')} has no valid medical images, skipping")
                
                # Replace with validated cases
                if validated_cases:
                    cases = validated_cases
                    logging.info(f"Validation reduced cases from {len(cases)} to {len(validated_cases)}")
                else:
                    logging.warning("No cases with valid medical images found after validation")
            
            output_file = os.path.join(out_dir, f"{modality_name}_cases.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cases, f, indent=2, ensure_ascii=False)
            logging.info(f"Saved {len(cases)} cases to {output_file}")
        else:
            logging.warning(f"No cases collected for modality '{modality_name}'")

    logging.info("Scraping finished.")
    if isinstance(scraper, SeleniumScraper):
        scraper.quit()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script interrupted by user")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")