# KnowledgeMap Tests

This directory contains unit tests for the KnowledgeMap document ingestion pipeline.

## Running Tests

### Run all tests
```bash
python3 -m unittest discover tests/ -v
```

### Run specific test file
```bash
python3 -m unittest tests.test_pdf_handler -v
```

### Run a specific test case
```bash
python3 -m unittest tests.test_pdf_handler.TestPDFProcessorFactory.test_get_processor_auto_selects_mineru
```

## Test Coverage

### PDF Handler Tests (`test_pdf_handler.py`)
- **17 tests** covering:
  - Abstract PDFProcessor interface
  - MinerUProcessor implementation
  - PyPDF2Processor implementation
  - PDF processor factory function
  - File processing and validation
  - End-to-end integration workflow

**Key Features Tested:**
- Dependency checking for different PDF processors
- Installation instructions retrieval
- PDF-to-markdown conversion workflow
- Processor auto-selection and fallback
- File validation (extension, existence)
- Library folder creation

## Test Design

The tests follow these principles:
1. **Isolation**: Each test is independent with no shared state
2. **Mocking**: External dependencies (MinerU, PyPDF2) are mocked to avoid requiring installation
3. **Temporary Files**: Tests use `tempfile` for file operations
4. **Cleanup**: All temporary resources are properly cleaned up
5. **Coverage**: Tests cover both success paths and edge cases

## Dependencies

The tests use Python's standard library:
- `unittest` - Test framework
- `unittest.mock` - Mocking support
- `tempfile` - Temporary file creation
- `pathlib` - Path handling

No additional test-specific dependencies are required.
