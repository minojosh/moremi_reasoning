# Moremi Reasoning

## Project Overview

Moremi Reasoning is a specialized medical image analysis system that uses AI to generate structured reasoning, reflection, and diagnostic answers from chest X-ray images and associated clinical information. The system integrates Google's Gemini AI to provide detailed analysis of medical images with a focus on maintaining structured output formats.

## Key Features

- **Medical Image Analysis**: Processes chest X-ray images alongside patient clinical data
- **Structured Reasoning**: Generates analysis in a standardized format with separate reasoning, reflection, and answer sections
- **Consolidated Results**: Creates both individual records and a consolidated JSON file containing all processed records
- **Transparent Processing**: Maintains detailed logs of processing activities

## Project Structure

```
moremi_reasoning/
├── logs/                   # Processing logs with timestamps
├── reports/                # Generated analysis results
├── src/                    # Source code
│   ├── main.py             # Main entry point for the application
│   ├── report_processor.py # Core processing logic
│   ├── settings.yaml       # Configuration settings
│   └── test_processor.py   # Testing utilities
├── utils/                  # Utility functions
├── reasoning_trace.py      # Reasoning trace functionality
└── .env                    # Environment variables
```

## How It Works

1. **Input**: The system takes chest X-ray images and associated patient data (age, gender, clinical history) as input
2. **Processing**: Images and patient data are processed by the AI model (Google's Gemini)
3. **Output**: Results are structured in a standardized JSON format with separate sections:
   ```json
   {
     "image": "path/to/image.jpg",
     "reasoning": "Detailed clinical reasoning about the image",
     "reflection": "Reflections on potential limitations of the analysis",
     "answer": "Concise diagnostic impression"
   }
   ```
4. **Consolidation**: Individual results are saved as separate JSON files and consolidated into a single JSON file for easier analysis

## Technical Implementation

### Report Processor

The core of the system is the `ReportProcessor` class which handles:

- Loading and parsing patient reports
- Processing images with the Gemini AI model
- Extracting structured sections (reasoning, reflection, answer) from AI responses
- Saving individual and consolidated results

### Output Format

The system ensures consistent output structure where:
1. The image path is always listed first
2. The reasoning section contains detailed clinical analysis
3. The reflection section discusses limitations and alternative considerations
4. The answer section provides a concise diagnostic impression

### AI Integration

The system uses Google's Gemini API with:
- Custom system prompts loaded from configuration
- Appropriate temperature and generation parameters for medical reasoning
- Proper handling of medical images and clinical context

## Usage

1. Set up environment variables in the `.env` file (API keys, etc.)
2. Prepare your image directory and clinical report data
3. Run the processor:
   ```python
   python src/main.py
   ```
4. Find individual results in the `reports/` directory and the consolidated JSON file with all records

## Usage Examples

# Run with default BS4 backend
```bash
python -m radiopedia_data.run
```

# Run with Selenium backend
```bash
python -m radiopedia_data.run --backend selenium
```

**Note:** Do not include square brackets literally; they indicate optional flags in usage help.

## Requirements

- Python 3.7+
- PIL (Pillow)
- Google Generative AI Python library
- PyYAML
- Other dependencies as specified in requirements.txt

## Logging

The system maintains detailed logs with timestamps in the `logs/` directory, tracking:
- Processing activities
- Errors and warnings
- API interactions
- File operations

## License

[Specify license information here]