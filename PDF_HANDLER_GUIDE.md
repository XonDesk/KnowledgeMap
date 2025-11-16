# PDF Handler Usage Guide

The PDF handler processes PDF files and converts them to markdown format using pluggable PDF processing tools.

## Quick Start

### Installation

Install MinerU (recommended for high-quality conversion):
```bash
pip install --upgrade pip
pip install uv
uv pip install -U "mineru[core]"
```

Or install PyPDF2 (fallback for basic text extraction):
```bash
pip install PyPDF2
```

### Basic Usage

#### Process a single PDF file
```bash
python3 pdf_handler.py /path/to/document.pdf
```

This will:
1. Auto-detect and use the best available PDF processor (MinerU → PyPDF2)
2. Convert the PDF to markdown
3. Save the result to `library/document.md`

#### Specify a PDF processor
```bash
# Use MinerU explicitly
python3 pdf_handler.py /path/to/document.pdf mineru

# Use PyPDF2 explicitly
python3 pdf_handler.py /path/to/document.pdf pypdf2
```

#### Process multiple PDFs via dispatcher
```bash
# Process all PDFs in a folder
python3 file_dispatcher.py /path/to/folder --log

# Process recursively
python3 file_dispatcher.py /path/to/folder --recursive --log
```

## Features

### MinerU Processor (Default)
- ✅ Preserves document structure (headings, paragraphs, lists)
- ✅ Extracts images and saves to `library/images/<pdf_name>/`
- ✅ Converts formulas to LaTeX
- ✅ Handles complex layouts (multi-column, headers/footers)
- ✅ Extracts tables with proper formatting
- ⚠️ Requires more dependencies

### PyPDF2 Processor (Fallback)
- ✅ Simple text extraction
- ✅ Lightweight with minimal dependencies
- ✅ Fast processing
- ⚠️ No layout preservation
- ⚠️ No image extraction
- ⚠️ Basic text-only output

## Output Format

All PDF processors generate markdown files with YAML frontmatter:

```markdown
---
source_file: document.pdf
converted_date: 2025-11-14 15:30:00
converter: MinerU
---

# Document Title

Content here...
```

## Adding a Custom PDF Processor

You can easily add your own PDF processing tool:

### 1. Create a new processor class

```python
from pdf_handler import PDFProcessor
from pathlib import Path

class MyCustomProcessor(PDFProcessor):
    """My custom PDF processor"""
    
    def check_dependencies(self) -> bool:
        """Check if required libraries are installed"""
        try:
            import my_pdf_library
            return True
        except ImportError:
            return False
    
    def get_installation_instructions(self) -> str:
        """Provide installation instructions"""
        return """
My Custom Processor Installation:
----------------------------------
    pip install my-pdf-library
"""
    
    def process_pdf(self, pdf_path: Path, output_path: Path) -> Path:
        """Convert PDF to markdown"""
        import my_pdf_library
        
        # Your conversion logic here
        markdown_content = my_pdf_library.convert(pdf_path)
        
        # Write output with frontmatter
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"---\\n")
            f.write(f"source_file: {pdf_path.name}\\n")
            f.write(f"converter: MyCustomProcessor\\n")
            f.write(f"---\\n\\n")
            f.write(markdown_content)
        
        return output_path
```

### 2. Register your processor

In `pdf_handler.py`, update the `get_pdf_processor()` function:

```python
def get_pdf_processor(processor_name: Optional[str] = None) -> PDFProcessor:
    processors = {
        'mineru': MinerUProcessor,
        'pypdf2': PyPDF2Processor,
        'mycustom': MyCustomProcessor,  # Add your processor here
    }
    # ... rest of the function
```

### 3. Use your processor

```bash
python3 pdf_handler.py /path/to/document.pdf mycustom
```

## Architecture

The PDF handler follows a **Strategy Pattern**:

```
PDFProcessor (Abstract Base Class)
    ├── check_dependencies() → bool
    ├── get_installation_instructions() → str
    └── process_pdf(pdf_path, output_path) → Path

Concrete Implementations:
    ├── MinerUProcessor
    ├── PyPDF2Processor
    └── YourCustomProcessor (add yours here!)

Factory Function:
    get_pdf_processor(processor_name=None) → PDFProcessor
        - Auto-selects first available processor
        - Or returns explicitly requested processor
```

This design makes it easy to:
- Add new PDF processing tools
- Swap processors without changing calling code
- Test processors independently
- Provide fallback options

## Troubleshooting

### "No PDF processor available"
Install at least one PDF processing library:
```bash
pip install "mineru[core]"  # Recommended
# or
pip install PyPDF2          # Fallback
```

### MinerU import errors
Make sure you have the `[core]` extras installed:
```bash
uv pip install -U "mineru[core]"
```

### Images not extracted
Only MinerU extracts images. PyPDF2 does text-only extraction.

### Poor quality output
Try MinerU instead of PyPDF2 for better layout preservation and structure detection.

## Integration with Dispatcher

The PDF handler integrates seamlessly with `file_dispatcher.py`:

1. Dispatcher detects `.pdf` files
2. Routes them to `pdf_handler.py`
3. PDF handler converts to markdown → `library/`
4. Dispatcher then calls `embed_documents.py` to generate embeddings
5. Embeddings stored in Neo4j for semantic search

This creates a complete pipeline: **PDF → Markdown → Embeddings → Neo4j**
