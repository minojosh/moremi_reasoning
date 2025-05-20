# Radiopaedia Data Scraper

This folder contains scripts to scrape case data from Radiopaedia.org using either BeautifulSoup (BS4) or Selenium.

## Prerequisites

1. Python 3.7+
2. Chrome browser (for Selenium backend)
3. virtualenv (optional, but recommended)

## Setup

1. Clone the repository and navigate to this directory:

   ```bash
   cd radiopedia_data
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required packages:

   ```bash
   pip install -r ../requirements.txt
   ```

4. Configure the modalities and keywords in `src/config/modalities.yaml`. Ensure it looks like:

   ```yaml
   modalities:
     CT:
       keywords:
         - "chest"
         - "abdomen"
     MRI:
       keywords:
         - "brain"
         - "spine"
   ```

## Usage

All scraping is driven via `run.py`. It will:
- Load your modalities and keywords from the YAML config
- Fetch case URLs for each keyword
- Download and parse each case page
- Save JSON per modality in this directory

### Basic (BS4) Backend

```bash
python run.py
```

### Limit number of cases

```bash
python run.py --max-cases 100
```

### Selenium Backend (dynamic content)

```bash
python run.py --backend selenium
```

If Selenium fails to initialize, `run.py` will fall back to the BS4 scraper automatically.

## Other Utility Scripts

- `scrape_radiopaedia.py`: simple function to fetch and parse Radiopaedia search pages for case URLs.
- `scrape_dental_cases.py`: dedicated Selenium-based scraper for dental/mammography keyword lists.

## Output

- `<MODALITY>_cases.json`: array of case data objects with fields:
  - `case_url`, `diagnosis`, `modality`, `age`, `gender`, `findings`, `discussion`, `images`, `image_details`, etc.

All output files are saved into the `radiopedia_data` directory.

---

Please report issues or feature requests to the project maintainer.
