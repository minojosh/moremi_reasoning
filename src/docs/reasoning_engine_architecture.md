# Reasoning Engine Architecture

This document provides a detailed overview of the `reasoning_engine.py` module, which is the core component of the Moremi Reasoning project. It is designed to be a reusable and extensible module for various multimodal reasoning tasks.

## Core Components

The reasoning engine is composed of several key classes that work together to manage configuration, interact with language models, and apply reasoning strategies.

### `ReasoningConfig`

This class centralizes all configuration management. It loads settings from YAML files, including model parameters, API endpoints, and prompt templates.

-   **Initialization**: Takes an optional `config_dir`, `config_file`, and `prompts_file`. If not provided, it defaults to the `src/config` directory.
-   **Configuration Loading**: It loads the main configuration file (e.g., `salesforce_config.yaml`) and the corresponding prompts file (e.g., `salesforce_prompts.yaml`).
-   **Error Handling**: Raises a `FileNotFoundError` if the specified configuration files do not exist.

### `MultimodalGPT`

This class is a client for interacting with multimodal language models. It handles API calls, including the encoding of images and the construction of messages.

-   **Initialization**: Requires a `ReasoningConfig` object. It retrieves the model name and API URL from the configuration.
-   **API Key Management**: It fetches the `OPEN_ROUTER_API_KEY` from the environment variables, raising a `ValueError` if it's not set.
-   **`call()` method**: The primary method for making API calls. It constructs a message payload that can include both text and image content.
    -   **Image Encoding**: It can handle both local file paths and remote URLs for images, encoding them into base64 format.
    -   **Parameterization**: API call parameters like `max_tokens` and `temperature` can be customized.
-   **`text_only_call()` method**: A convenience method for making text-only API calls, typically used for verification tasks with a temperature of 0.0 for deterministic output.
-   **`retry_call()` method**: Implements a simple retry mechanism for API calls to handle transient network issues.

### `ReasoningStrategies`

This class encapsulates a set of predefined reasoning strategies that can be applied to improve the accuracy of the model's responses.

-   **Strategy Loading**: It loads strategies from the prompts configuration file. Each strategy consists of a name and a prompt template.
-   **`apply_strategy()` method**: Applies a single reasoning strategy. It formats the strategy prompt with the current context and makes a new API call.
-   **`apply_all_strategies()` method**: Sequentially applies a list of strategies until a correct answer is found or the maximum number of attempts is reached. It uses the `check_answer_accuracy` function to validate the responses against a ground truth.

## Helper Functions

-   **`encode_image(image_path, image_dir=None)`**: Encodes an image from a local file or a URL into a base64 string.
-   **`extract_final_conclusion(text, content_type="general")`**: A utility function to extract the most relevant part of a model's response, filtering out conversational filler and reasoning steps.
-   **`check_answer_accuracy(response, reference, gpt_instance, ...)`**: Compares the model's response to a reference (ground truth) answer to determine its correctness.
-   **`synthesize_natural_reasoning(...)`**: Converts a series of reasoning steps into a coherent, human-readable explanation.
-   **`synthesize_final_response(...)`**: Generates the final, polished response based on the synthesized reasoning.

## Workflow

A typical reasoning pipeline using this engine follows these steps:

1.  **Initialization**: A `ReasoningConfig` object is created to load the necessary configurations.
2.  **GPT Client**: A `MultimodalGPT` instance is created with the loaded configuration.
3.  **Initial Call**: An initial API call is made with the input data (text and/or images).
4.  **Accuracy Check**: The response is checked for accuracy against a ground truth answer.
5.  **Reasoning Strategies**: If the initial response is incorrect, `ReasoningStrategies` are applied to try to find the correct answer.
6.  **Synthesize Output**: The final reasoning trace is synthesized into a natural language explanation and a final response is generated.
