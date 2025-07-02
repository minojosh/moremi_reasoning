from bs4 import BeautifulSoup
import requests
import time
import json
import os
modalities = ["mri", "ct", "x-ray", "ultrasound", "mammography"]
# modality = [modality for modality in modalities if modality in "mri"][0]  # Default to MRI if not specified
modality = "mammography"  # Change this to the desired modality
def scrape_radiopaedia(query=modality, page=1, scope="cases"):
    """
    Scrape search results from Radiopaedia.org
    
    Args:
        query (str): Search term
        page (int): Page number
        scope (str): Search scope (cases, articles, etc.)
        
    Returns:
        soup (BeautifulSoup): Parsed HTML content
    """
    base_url = f'https://radiopaedia.org/search?lang=us&page={page}&q={query}&scope={scope}'
    print(base_url)
    
    # Set headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    # Make the request with headers
    response = requests.get(base_url, headers=headers)
    
    # Check if request was successful
    if response.status_code == 200:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    else:
        print(f"Error: Status code {response.status_code}")
        return None

def get_total_pages(soup):
    """
    Extract the total number of pages from pagination
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        
    Returns:
        int: Total number of pages
    """
    # Find pagination elements - looking for all page links
    pagination_links = soup.select('div[role="navigation"][class*="pagination"] a[aria-label^="Page"]')
    
    if not pagination_links:
        return 1
    
    # Get the last page number from the pagination links
    page_numbers = []
    for link in pagination_links:
        # Extract the page number from aria-label attribute
        aria_label = link.get('aria-label', '')
        if aria_label.startswith('Page '):
            try:
                page_number = int(aria_label.replace('Page ', '').strip())
                page_numbers.append(page_number)
            except ValueError:
                continue
    
    # Return the maximum page number found, or 1 if none found
    return max(page_numbers) if page_numbers else 1

def extract_case_urls(soup):
    """
    Extract only case URLs from the search results
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        
    Returns:
        list: List of case URLs
    """
    case_urls = []
    
    # Find all case elements using the specific class for cases
    case_elements = soup.select('a.search-result.search-result-case')
    
    for case in case_elements:
        if case and 'href' in case.attrs:
            # Extract the URL and ensure it's absolute
            case_url = case['href']
            if not case_url.startswith('http'):
                case_url = 'https://radiopaedia.org' + case_url
            case_urls.append(case_url)
    
    return case_urls

def load_existing_urls(filename=f"{modality}_case_urls.json"):
    """
    Load existing URLs from file if it exists
    
    Args:
        filename (str): Input filename
        
    Returns:
        set: Set of existing URLs
    """
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_to_json(data, filename=f"{modality}_case_urls.json"):
    """
    Save data to JSON file
    
    Args:
        data (list): Data to save
        filename (str): Output filename
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(list(data), f, indent=4, ensure_ascii=False)
    print(f"Data saved to {filename}")

if __name__ == "__main__":
    # List of dental-related keywords
    # Use the selected modality to determine which keywords to search for
    modality_keywords = {
        # "mri": ["mri", "magnetic resonance imaging", "magnetic resonance", "contrast_mri", "mri scan", "mri imaging", "mri brain", "mri spine", "mri abdomen", "mri pelvis"],
        # "ct": ["ct", "computed tomography", "computed tomographic", "ct scan"],
        # "x-ray": ["x-ray", "xray","chest x-ray", "spine x-ray"],
        # "ultrasound": ["ultrasound"],
        "mammography": ["breast bi-rad"]
    }
    # Select keywords for the current modality
    search_keywords = modality_keywords.get(modality, ["mri"])
    print(f"Using modality: {modality}")
    print(f"Search keywords: {search_keywords}")
    
    
    # Load existing URLs to avoid duplicates
    all_case_urls = load_existing_urls()
    initial_count = len(all_case_urls)
    print(f"Loaded {initial_count} existing URLs")
    
    # Scrape for each keyword
    for keyword in search_keywords:
        print(f"\nSearching for keyword: {keyword}")
        
        # Get the first page to determine total pages
        soup = scrape_radiopaedia(query=keyword, page=1)
        if not soup:
            print(f"Failed to retrieve results for '{keyword}', skipping...")
            continue
        
        # Get total number of pages
        total_pages = get_total_pages(soup)
        print(f"Found {total_pages} pages of results for '{keyword}'")
        
        # Extract URLs from first page
        urls = extract_case_urls(soup)
        new_urls = [url for url in urls if url not in all_case_urls]
        all_case_urls.update(new_urls)
        print(f"Found {len(new_urls)} new URLs on page 1")
        
        # Scrape remaining pages
        for page in range(2, total_pages + 1):
            print(f"Scraping page {page}/{total_pages}...")
            soup = scrape_radiopaedia(query=keyword, page=page)
            
            if soup:
                urls = extract_case_urls(soup)
                new_urls = [url for url in urls if url not in all_case_urls]
                all_case_urls.update(new_urls)
                print(f"Found {len(new_urls)} new URLs on page {page}")
                
                # Be nice to the server
                if page < total_pages:
                    time.sleep(2)
    
    # Save results
    save_to_json(all_case_urls)
    print(f"\nTotal unique case URLs scraped: {len(all_case_urls)}")
    print(f"New URLs added: {len(all_case_urls) - initial_count}")
