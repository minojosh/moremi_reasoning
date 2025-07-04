# Radiopedia Pipeline

A unified, modular pipeline for scraping and processing medical case data from Radiopaedia.org.

## Features

- **Modular Design**: Separate components for URL scraping, case data extraction, and data processing
- **CLI Interface**: Easy-to-use command-line interface with flexible options
- **Parallel Processing**: Support for processing multiple modalities simultaneously
- **Configuration-Driven**: YAML-based configuration for easy customization
- **Robust Error Handling**: Comprehensive logging and error management
- **Data Validation**: Automatic restructuring and filtering of case data

## Quick Start

### Process a single modality (default: all steps)
```bash
python run_radiopedia_pipeline.py mammography
```

### Process with custom limit
```bash
python run_radiopedia_pipeline.py mammography --limit 100
```

### Process all modalities in parallel
```bash
python run_radiopedia_pipeline.py all --limit 50
```

### Run specific pipeline steps
```bash
# Only scrape URLs
python run_radiopedia_pipeline.py ct --steps scrape-urls

# Only scrape URLs and cases (skip processing)
python run_radiopedia_pipeline.py mammography --steps scrape-urls scrape-cases
```

## Available Modalities

- mammography
- x-ray
- ultrasound
- ct
- mri
- pathology
- angiography

## Pipeline Steps

1. **scrape-urls**: Collect case URLs from Radiopaedia search results
2. **scrape-cases**: Extract detailed case data including images and metadata  
3. **process-data**: Restructure and filter data for analysis

**Default Steps**: By default, the pipeline runs all three steps for a complete end-to-end process.

## Configuration

The pipeline uses configuration files in `src/config/`:

- `modalities.yaml`: Defines modalities and their search keywords
- `radiopedia_config.yaml`: Pipeline settings and parameters

## Output Structure

Data is saved to timestamped run directories for easy organization and comparison:

```
radiopedia/
└── runs/
    └── YYYY-MM-DD/
        └── HH-MM-SS/
            ├── 01_scraped_urls/
            │   └── {modality}_case_urls.json
            ├── 02_scraped_cases/
            │   └── {modality}_cases_collected.json
            ├── 03_restructured_data/
            │   └── {modality}_cases_restructured.json
            └── 04_processed_data/
                ├── {modality}_only_cases.json
                └── {modality}_failed_cases.json
```

### Organized Directory Structure

Each pipeline run creates a timestamped directory with clearly organized subdirectories:
- **01_scraped_urls**: Raw URLs collected from search results
- **02_scraped_cases**: Complete case data extracted from individual pages
- **03_restructured_data**: Data reorganized and grouped by study
- **04_processed_data**: Final filtered and validated cases ready for analysis

### Timestamped Runs

Each pipeline execution creates a unique timestamped directory:
- **Date Structure**: `YYYY-MM-DD` (e.g., `2025-07-01`)
- **Time Structure**: `HH-MM-SS` (e.g., `14-30-25`)
- **Full Path Example**: `src/data/radiopedia/runs/2025-07-01/14-30-25/`

This ensures all artifacts from a single run are grouped together and easily identifiable.

## Requirements

- Python 3.7+
- Chrome/Chromium browser
- ChromeDriver
- Required packages: selenium, requests, beautifulsoup4, tqdm, pyyaml

## Architecture

The pipeline follows a modular architecture:

- **URL Scraper** (`src/providers/radiopedia/url_scraper.py`): Collects case URLs
- **Case Scraper** (`src/providers/radiopedia/case_scraper.py`): Extracts case data
- **Data Processor** (`src/utils/preprocess_radiopedia_data.py`): Restructures and filters data
- **Configuration Loader** (`src/utils/config_loader.py`): Manages YAML configurations
- **Path Manager** (`src/utils/path_config.py`): Handles file paths and directories
