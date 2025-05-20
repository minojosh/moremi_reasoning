# Moremi Reasoning - Technical Documentation

## System Architecture

Moremi Reasoning operates through a modular architecture designed for processing medical images and clinical data. The system follows a pipeline architecture that processes each case individually and then consolidates the results.

## Core Components

### Report Processor

The `ReportProcessor` class serves as the backbone of the system, orchestrating the entire processing workflow:

```
ReportProcessor
├── setup_logging()         # Configures timestamped logging
├── load_system_prompt()    # Loads AI prompting instructions
├── setup_gemini()          # Initializes the Gemini API
├── clean_report_text()     # Sanitizes clinical reports
├── load_reports()          # Loads patient data
├── get_image_path()        # Resolves image file paths
├── encode_image()          # Prepares images for AI processing
├── extract_report_info()   # Extracts relevant patient data
├── parse_response()        # Parses structured data from AI responses
├── generate_reasoning()    # Core AI interaction function
├── save_reasoning()        # Saves individual case results
├── save_consolidated_records() # Creates the master results file
└── process_reports()       # Main processing loop
```

### Data Flow

1. **Input Data Loading**: Patient reports are loaded from a JSON file specified at initialization
2. **Image Processing**: X-ray images are loaded and encoded for AI processing
3. **Clinical Data Extraction**: Relevant patient information is extracted and sanitized
4. **AI Processing**: Images and clinical data are sent to the Gemini AI model
5. **Response Parsing**: AI responses are parsed into structured sections
6. **Result Storage**: Results are stored as individual files and consolidated

### Response Parsing Logic

The system uses a sophisticated parsing approach to extract structured content from AI responses:

1. **Tag-based extraction**: Primarily looks for content between `<reasoning>`, `<reflection>`, and `<answer>` tags
2. **Header-based fallback**: If tags are missing, looks for section headers like "Reasoning:", "Reflection:", "Answer:"
3. **Intelligent splitting**: If neither tags nor headers are present, splits the content proportionally

## Configuration

### System Prompt

The system uses a template-based prompt system defined in `settings.yaml`. This prompt guides the AI to generate appropriately structured responses.

### API Configuration

The Gemini API is configured with specific parameters optimized for medical reasoning:
- Temperature: 0.6 (balanced between creativity and consistency)
- Top-p: 0.8 (nucleus sampling parameter)
- Top-k: 40 (limits token selection pool)
- Max tokens: 2048 (sufficient for detailed medical analysis)

## Output Structure

### Individual Case Files

Each processed case generates:
1. A JSON file with the structured data
2. A human-readable text file with the same information in plain text

### Consolidated JSON

The master JSON file follows this structure:
```json
{
  "patient_id_1": {
    "image": "path/to/image1.jpg",
    "reasoning": "...",
    "reflection": "...",
    "answer": "..."
  },
  "patient_id_2": {
    "image": "path/to/image2.jpg",
    "reasoning": "...",
    "reflection": "...",
    "answer": "..."
  },
  ...
}
```

## Error Handling

The system implements comprehensive error handling:
- Image loading failures are gracefully handled
- API errors are caught and logged
- Parsing errors fall back to progressively simpler methods
- All errors are logged with detailed information

## Performance Considerations

- Images are converted to RGB mode as needed for API compatibility
- Text content is sanitized to remove unnecessary metadata
- Processing is done sequentially to avoid API rate limiting
- The consolidated file is only written once at the end of processing

## Future Enhancements

Potential areas for system improvement:
1. Parallel processing for higher throughput
2. Enhanced error recovery mechanisms
3. Support for additional medical imaging modalities
4. Interactive review and correction interface
5. Integration with medical record systems

## Development Guidelines

When extending the system:
1. Maintain the structured output format
2. Ensure proper error handling
3. Update logging for new components
4. Test with a variety of medical images and reports
5. Validate AI responses against medical expertise