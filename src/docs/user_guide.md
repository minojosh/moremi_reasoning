# Moremi Reasoning - User Guide

This guide will help you get started with using the Moremi Reasoning system for AI-assisted medical image analysis.

## Getting Started

### Prerequisites

Before using Moremi Reasoning, ensure you have:

1. Python 3.7 or higher installed
2. Required packages installed (`pip install -r requirements.txt`)
3. A Google API key with access to Gemini API
4. Medical images (chest X-rays) in a proper directory structure
5. Clinical reports in the required JSON format

### Environment Setup

1. Create or edit the `.env` file in the project root:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

2. Verify your image paths are correctly configured in your report data

## Running the System

### Basic Usage

To process medical images and generate AI reasoning:

```bash
python src/main.py --reports_path /path/to/reports.json --image_base_path /path/to/images/
```

### Command Line Arguments

- `--reports_path`: Path to the JSON file containing patient reports
- `--image_base_path`: Base path to the directory containing X-ray images
- `--log_level`: (Optional) Set logging level (default: INFO)
- `--model_name`: (Optional) Specify a different Gemini model (default: gemini-1.5-flash)

## Input Format

### Report JSON Structure

Your input JSON file should have the following structure:

```json
{
  "patient_id_1": {
    "patient_infomation": {
      "age": 45,
      "gender": "Male",
      "clinical_history": "Patient presented with chest pain",
      "full_text": "Complete report text including clinical information..."
    }
  },
  "patient_id_2": {
    "patient_infomation": {
      "age": 67,
      "gender": "Female",
      "clinical_history": "Shortness of breath",
      "full_text": "Complete report text including clinical information..."
    }
  }
}
```

### Image Requirements

- Images should be in JPG or PNG format
- Named according to patient IDs (e.g., `patient_id_1.jpg`)
- Located in the directory specified by `image_base_path`

## Understanding the Output

### Output Locations

After processing, you'll find:

1. **Individual JSON files**: `/reports/{patient_id}.json`
2. **Individual text files**: `/reports/{patient_id}.txt`
3. **Consolidated JSON file**: `/reports/all_processed_records_{timestamp}.json`
4. **Log files**: `/logs/report_processor_{timestamp}.log`

### Output Structure

Each result follows this structured format:

1. **Image**: Path to the processed X-ray image
2. **Reasoning**: Detailed medical reasoning about the image findings
3. **Reflection**: Discussion of limitations and alternative considerations
4. **Answer**: Concise diagnostic impression

### Example Output

```json
{
  "image": "/path/to/images/patient_123.jpg",
  "reasoning": "The chest X-ray shows clear lung fields with no evidence of consolidation...",
  "reflection": "While the X-ray appears normal, certain conditions may not be visible...",
  "answer": "Normal chest X-ray with no evidence of acute cardiopulmonary disease."
}
```

## Troubleshooting

### Common Issues

1. **API Key errors**: Verify your API key is correctly set in the `.env` file
2. **Image loading errors**: Check that image paths and formats are correct
3. **JSON parsing errors**: Ensure your input JSON follows the required structure
4. **Missing sections in output**: Check the log files for parsing issues

### Log Analysis

Review the log files in the `/logs` directory to identify issues:
- INFO level entries show normal processing
- WARNING level entries indicate potential issues
- ERROR level entries show processing failures

## Best Practices

1. **Image Quality**: Use high-quality, properly oriented X-ray images
2. **Clinical Context**: Provide thorough clinical information for better results
3. **Regular Updates**: Keep the system and its dependencies updated
4. **Validation**: Always have medical professionals review the AI-generated results

## Advanced Usage

### Customizing the System Prompt

Edit the `src/settings.yaml` file to customize how the AI approaches the analysis.
This can help emphasize particular aspects of the reasoning or guide the AI to focus on specific medical concerns.

### Processing Subsets of Data

To process only specific patients, you can create a filtered JSON file containing only the records you want to analyze.

## Feedback and Improvement

The Moremi Reasoning system improves with feedback. If you notice issues with the AI analysis:
1. Document the case ID and specific issue
2. Note any particular patterns or edge cases
3. Submit feedback through the appropriate channels