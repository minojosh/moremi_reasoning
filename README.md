# Moremi Reasoning Engine

This project contains a suite of tools and pipelines for multimodal reasoning, designed to process and interpret complex data from various sources, including handwritten documents, business forms, and medical images. The core of the project is a reusable `ReasoningEngine` that leverages large language models (LLMs) to perform tasks like Optical Character Recognition (OCR), question answering, and diagnostic analysis.

## Project Structure

- **`run_reasoning_pipeline.py`**: The main entry point for all data processing pipelines.
- **`src/`**: Contains the core source code.
  - **`core/`**: Houses the central `reasoning_engine.py` and other key modules.
  - **`providers/`**: Contains data-specific provider modules for different datasets (Handwriting, Salesforce, Radiopedia).
  - **`config/`**: YAML configuration files for models, prompts, and settings.
  - **`data/`**: Raw and processed data used by the pipelines.
  - **`docs/`**: Detailed documentation about the project architecture and components.
  - **`logs/`**: Output logs from pipeline runs, organized by process name.
  - **`utils/`**: Utility functions, including the custom logger.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd moremi_reasoning
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
    *Note: Ensure you have separate `requirements.txt` files for each specific provider if they have unique dependencies.*

3.  **Configure Environment Variables:**
    Create a `.env` file in the project root and add your API keys:
    ```
    OPEN_ROUTER_API_KEY="your_api_key_here"
    ```

## Running the Reasoning Pipelines

The `run_reasoning_pipeline.py` script is the unified entry point for executing all reasoning tasks. It provides a consistent command-line interface for the different data providers.

### General Usage

The basic command structure is:
```bash
python run_reasoning_pipeline.py <pipeline_name> [options]
```

-   **`<pipeline_name>`**: The name of the pipeline to run (`handwriting`, `salesforce`, `radiopedia`).
-   **`[options]`**: Common and pipeline-specific arguments.

### Common Options

-   `--limit <N>`: Process only the first `N` items.
-   `--no-resume`: Ignores any saved progress and starts the pipeline from the beginning.
-   `--config <file_path>`: Specify a custom configuration file.

### Pipeline-Specific Examples

#### Handwriting OCR

Processes handwritten documents to perform OCR and answer questions.

```bash
# Run the handwriting pipeline on the first 10 documents
python run_reasoning_pipeline.py handwriting --limit 10
```

#### Salesforce Document QA

Processes Salesforce-related documents for question answering.

```bash
# Run the Salesforce pipeline using word-level granularity
python run_reason_pipeline.py salesforce --granularity 1 --limit 50
```

#### Radiopedia Medical Imaging Analysis

Analyzes medical images from Radiopedia and generates diagnostic reports.

```bash
# Run on all modalities
python run_reasoning_pipeline.py radiopedia --limit 5

# Run on a specific modality (e.g., mammography)
python run_reasoning_pipeline.py radiopedia --modality mammography --limit 20
```
