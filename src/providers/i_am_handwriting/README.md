## Handwriting OCR Reasoning (`handwriting_ocr_reasoning.py`)

This script provides a pipeline for performing Optical Character Recognition (OCR) on handwritten text images, generating questions about the content, and using a multimodal AI model to answer those questions with a chain-of-thought reasoning process. It's designed to work with the IAM Handwriting Database.

### Core Functionality:

1.  **Data Ingestion**:
    *   Loads handwritten text images (PNG, JPG, JPEG) from a specified directory (`src/data/i_am_handwriting/cropped_handwritten` by default).
    *   Loads corresponding XML files containing ground truth transcriptions from a specified directory (`src/data/i_am_handwriting/xml` by default).
    *   Matches image files with their XML counterparts based on filenames.

2.  **Configuration**:
    *   Uses `ReasoningConfig` (from `src/core/reasoning_engine.py`) to load pipeline settings from `handwriting_config.yaml` and prompt templates from `handwriting_prompts.yaml` (both located in `src/config/`).
    *   Initializes `MultimodalGPT` (from `src/core/reasoning_engine.py`) for interacting with the AI model.
    *   Initializes `ReasoningStrategies` (from `src/core/reasoning_engine.py`) to apply various reasoning refinement techniques.
    *   Initializes `OCRQuestionGenerator` (from `src/providers/salesforce_ocr/ocr_question_generator.py`) to dynamically create questions about the handwriting images.

3.  **Processing per Sample (`process_sample_ocr` function)**:
    *   **Ground Truth Extraction**: Uses `GroundTruthExtractor` (from `src/providers/i_am_handwriting/iam_utils.py`) to parse the XML file and extract the full handwritten text transcription. This serves as the "ground truth answer" for comparison, although the primary task is to answer a *generated* question.
    *   **Question Generation**:
        *   Invokes `OCRQuestionGenerator` to create a question about the image. The difficulty level of the question (e.g., "handwriting_basic", "handwriting_detailed") is chosen randomly.
        *   If question generation fails, a default OCR question from the prompts configuration is used.
    *   **Initial AI Model Call**:
        *   Formats an initial prompt using a template (e.g., `query_prompt_init` from `handwriting_prompts.yaml`) and the generated question.
        *   Sends the image and the formatted prompt to the `MultimodalGPT` instance to get an initial answer.
    *   **Reasoning Strategy Application**:
        *   Applies a series of reasoning strategies (defined in `ReasoningStrategies`) to refine the initial answer. These strategies might involve re-prompting the model with different perspectives or focusing on specific aspects of the image or previous responses.
        *   The context for these strategies includes the image, the generated question, and the current model response.
    *   **Natural Reasoning Synthesis**:
        *   Uses `synthesize_natural_reasoning` (from `src/core/reasoning_engine.py`) to convert the history of AI responses (including initial answer and strategy-based refinements) into a more human-like, narrative thought process.
    *   **Final Response Generation**:
        *   Formats a final prompt (e.g., `final_response_prompt` from `handwriting_prompts.yaml`) using the synthesized natural reasoning and the original generated question.
        *   Makes a text-only call to `MultimodalGPT` to get the final, consolidated response from the AI.
    *   **Conclusion Extraction**:
        *   Uses `extract_final_conclusion` (from `src/core/reasoning_engine.py`) to pull out the most direct answer from the AI's final verbose response.
    *   **Result Compilation**: Stores a dictionary containing:
        *   Image ID, image path, XML path.
        *   The `Generated Question` posed to the model.
        *   The `Ground_True_Answer` (full transcription from XML).
        *   `Complex_CoT`: The synthesized natural reasoning text.
        *   `Response`: The final verbose response from the model.
        *   `Extracted_Answer`: The concise answer extracted from the final response.
        *   `Query_History`: A list of all prompts sent to the AI.
        *   `Response_History`: A list of all responses received from the AI.
        *   `Strategies_Used`: A list of reasoning strategies applied.
        *   Status (`success` or `error` with details).

4.  **Execution Management (`run_handwriting_ocr_reasoning` function)**:
    *   **Concurrency**: Uses a `ThreadPoolExecutor` to process multiple image samples in parallel, speeding up the overall pipeline. The number of worker threads is configurable.
    *   **Progress Tracking & Resumption**:
        *   Utilizes `ProgressTracker` (from `src/providers/i_am_handwriting/iam_utils.py`) to keep track of successfully processed image IDs in a `.progress` file. This allows the script to be interrupted and resumed later, skipping already processed samples.
        *   The `--no-resume` command-line flag can disable this behavior.
    *   **Incremental Results Saving**:
        *   Employs `IncrementalResultSaver` (from `src/providers/i_am_handwriting/iam_utils.py`) to save the results of each processed sample to a JSON file as they become available. This prevents data loss if the script crashes.
        *   The results file is timestamped (e.g., `handwriting_qna_results_YYYYMMDD_HHMMSS.json`).
        *   Backs up existing results files before starting a new run (if resuming).
    *   **Recovery**:
        *   Uses `RecoveryManager` (from `src/providers/i_am_handwriting/iam_utils.py`) to detect incomplete previous runs by looking for `.progress` files without corresponding full processing.
    *   **Output**:
        *   Saves detailed results for each sample in the main JSON output file.
        *   Generates a simplified JSON output file (e.g., `handwriting_qna_results_..._simplified.json`) containing key fields for easier analysis.
        *   Prints processing statistics (total processed, successful, errors) to the console.

### Key Dependencies and Concepts:

*   **`src.core.reasoning_engine`**:
    *   `ReasoningConfig`: Manages loading of configuration files (`*.yaml`) that define model parameters, API endpoints, file paths, and prompt templates.
    *   `MultimodalGPT`: A client class to interact with a multimodal GPT model (likely via an API like OpenRouter), handling image encoding and API calls.
    *   `ReasoningStrategies`: A class that encapsulates different methods (defined by prompts) to refine or re-evaluate the AI's responses. Examples from the broader system include "Backtracking," "Exploring New Paths," etc.
    *   `extract_final_conclusion`: A utility to parse the AI's verbose output and extract the core answer.
    *   `synthesize_natural_reasoning`: A function to transform a series of AI interactions into a coherent, human-readable thought process.
*   **`src.providers.i_am_handwriting.iam_utils`**:
    *   `GroundTruthExtractor`: Specifically designed to parse XML files from the IAM Handwriting Database to get the transcribed text.
    *   `ProgressTracker`: Manages a `.progress` file to log processed items, enabling resumption of interrupted jobs.
    *   `IncrementalResultSaver`: Saves results one by one to a JSON file, often using file locking (`fcntl`) for safety in concurrent environments.
    *   `RecoveryManager`: Helps identify and potentially resume or manage data from previous incomplete runs.
*   **`src.providers.salesforce_ocr.ocr_question_generator`**:
    *   `OCRQuestionGenerator`: A class responsible for generating diverse questions about an image, likely tailored for OCR tasks. It might have different templates or logic for various "difficulty levels" or "content types" (e.g., "handwriting").

### Command-Line Arguments:

*   `--config`: Path to a specific `reasoning_config.yaml` file for handwriting. Defaults to `handwriting_config.yaml` in the `src/config/` directory.
*   `--limit`: An integer to limit the number of images processed (useful for testing).
*   `--no-resume`: A flag to disable the resume functionality and start processing from scratch, ignoring any previous progress files.

### How to Use This Script

This guide outlines the steps to set up and run the `handwriting_ocr_reasoning.py` script.

1.  **Prerequisites:**
    *   **Python Environment**: Ensure a compatible Python version is installed (e.g., Python 3.8+).
    *   **Dependencies**: Install required packages. From the project root (`/home/justjosh/Turing-Test/moremi_reasoning/`), run:
        ```bash
        pip install -r src/requirements.txt
        ```
        *(Note: The `requirements.txt` is currently located in the `src/` directory. While functional, standard practice often places this at the project root. Consider if this location serves a specific purpose for your project structure.)*
    *   **API Key**: Securely manage your `OPEN_ROUTER_API_KEY`. The script loads it from a `.env` file located at the project root (`/home/justjosh/Turing-Test/moremi_reasoning/.env`). This file should contain:
        ```
        OPEN_ROUTER_API_KEY="your_actual_api_key_here"
        ```
        *Why a `.env` file?* This method keeps sensitive credentials out of version control (ensure `.env` is in your `.gitignore`!) and allows for easy environment-specific configuration.
    *   **Data**: The IAM Handwriting dataset images and their corresponding XML annotation files are expected. Configure their paths in `src/config/handwriting_config.yaml` (see step 2). Default example paths are `src/data/i_am_handwriting/cropped_handwritten/` for images and `src/data/i_am_handwriting/xml/` for XMLs.

2.  **Configuration:**
    *   The primary configuration file for this script is `src/config/handwriting_config.yaml`. **This file is the source of truth for critical parameters.** Review and customize it carefully. Key settings include:
        *   `model_name`: Specifies the AI model (e.g., "google/gemini-2.0-flash-001").
        *   `api_url`: The API endpoint for the chosen model.
        *   `images_dir`, `xml_dir`: **Crucially, set these to the correct absolute or relative paths where your image and XML data are stored.**
        *   `num_processes`: Adjust for parallel processing capability.
        *   `limit_num`: Useful for testing with a smaller subset of images. Set to `null` or remove to process all.
        *   `results_dir`, `logs_dir`: Define where outputs and log files are stored.
    *   AI behavior and prompt templates are managed in `src/config/handwriting_prompts.yaml`. Modify this if you need to alter how the AI generates questions, performs reasoning, or formats its responses.

3.  **Running the Script:**
    *   It's recommended to run the script from the **project root directory** (`/home/justjosh/Turing-Test/moremi_reasoning/`). The script is designed to correctly resolve internal project paths when run this way.
    *   Execute from the terminal:
        ```bash
        python src/providers/i_am_handwriting/handwriting_ocr_reasoning.py [OPTIONS]
        ```
    *   **Available Command-Line Options:**
        *   `--config /path/to/your/custom_handwriting_config.yaml`: Override the default configuration file.
        *   `--limit N`: Process only the first `N` image-XML pairs (e.g., `--limit 10`).
        *   `--no-resume`: Start a fresh run, ignoring any previously saved progress. Useful for forcing reprocessing.

4.  **Output**:
    *   **Console Logs**: Real-time progress, processing statistics, and any critical errors will be displayed in the console during execution.
    *   **Results Files**: Detailed outputs are saved in timestamped JSON files (e.g., `handwriting_qna_results_YYYYMMDD_HHMMSS.json`) within the directory specified by `results_dir` in your configuration (default: `results/`). A simplified version (e.g., `..._simplified.json`) is also generated.
    *   **Progress File**: To enable resumption, a `.progress` file (e.g., `handwriting_qna_results_YYYYMMDD_HHMMSS.progress`) is created alongside the results file, tracking successfully processed items.
    *   **Log Files**: The script contributes to the general project logs, typically found in the directory specified by `logs_dir` in `handwriting_config.yaml` (default: `logs/`). Look for entries timestamped during the script's execution for detailed diagnostic information. The script itself also generates timestamped log files specifically for its runs (e.g., `handwriting_ocr_YYYYMMDD_HHMMSS.log` within the configured `logs_dir`).

### Workflow Summary:

For each image-XML pair:
1.  Load image and extract ground truth text from XML.
2.  Generate a question about the image's handwritten content.
3.  Send the image and question to the AI for an initial answer.
4.  Apply reasoning strategies to refine the answer.
5.  Synthesize the reasoning steps into a natural language explanation.
6.  Generate a final, polished answer based on the synthesized reasoning.
7.  Extract a concise answer from this final response.
8.  Save all data (question, ground truth, AI interactions, final answer, etc.) to results files.

The script is built for robustness, allowing for parallel processing, interruption and resumption, and incremental saving of results.
