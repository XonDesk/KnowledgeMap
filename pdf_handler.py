#!/usr/bin/env python3
"""
PDF file handler for file_dispatcher.py
Processes .pdf files using pluggable PDF processing tools.
Converts them to markdown and saves to library/ folder.

Default Implementation: MinerU (https://github.com/opendatalab/MinerU)

To use a different PDF processing tool:
1. Create a new class that inherits from PDFProcessor
2. Implement the process_pdf() method
3. Update get_pdf_processor() to return your processor
"""
import sys
import logging
import os
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Optional
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class PDFProcessor(ABC):
    """Abstract base class for PDF processing implementations"""
    
    @abstractmethod
    def process_pdf(self, pdf_path: Path, output_path: Path) -> Path:
        """
        Process a PDF file and generate markdown output.
        
        Args:
            pdf_path: Path to the input PDF file
            output_path: Path where the markdown file should be saved
            
        Returns:
            Path to the generated markdown file
            
        Raises:
            Exception: If processing fails
        """
        pass
    
    @abstractmethod
    def check_dependencies(self) -> bool:
        """
        Check if required dependencies are installed.
        
        Returns:
            True if dependencies are available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_installation_instructions(self) -> str:
        """
        Get instructions for installing the processor.
        
        Returns:
            String with installation instructions
        """
        pass


class MinerUProcessor(PDFProcessor):
    """PDF processor using MinerU (https://github.com/opendatalab/MinerU)"""
    
    def check_dependencies(self) -> bool:
        """Check if MinerU is installed"""
        try:
            import magic_pdf
            return True
        except ImportError:
            return False
    
    def get_installation_instructions(self) -> str:
        """Get MinerU installation instructions"""
        return """
MinerU Installation Instructions:
----------------------------------
Using pip:
    pip install --upgrade pip
    pip install uv
    uv pip install -U "mineru[core]"

Using source:
    git clone https://github.com/opendatalab/MinerU.git
    cd MinerU
    uv pip install -e .[core]

For more information, visit: https://github.com/opendatalab/MinerU
"""
    
    def process_pdf(self, pdf_path: Path, output_path: Path) -> Path:
        """
        Process PDF using MinerU.
        
        Args:
            pdf_path: Path to the input PDF file
            output_path: Path where the markdown file should be saved
            
        Returns:
            Path to the generated markdown file
        """
        try:
            from magic_pdf.pipe.UNIPipe import UNIPipe
            from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
            import json
        except ImportError as e:
            logging.error(f"MinerU import failed: {e}")
            raise ImportError(
                "MinerU (magic-pdf) is not installed. "
                f"{self.get_installation_instructions()}"
            )
        
        logging.info(f"Processing PDF with MinerU: {pdf_path.name}")
        
        # Create a temporary directory for MinerU output
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # MinerU requires specific directory structure
            # It will create subdirectories for output
            pdf_name = pdf_path.stem
            
            try:
                # Read the PDF file
                logging.info(f"Reading PDF file: {pdf_path}")
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                
                # Initialize MinerU reader/writer
                logging.info(f"Initializing MinerU pipeline")
                reader_writer = DiskReaderWriter(str(temp_path))
                
                # Create MinerU pipeline
                # UNIPipe automatically handles layout detection and conversion
                pipe = UNIPipe(
                    pdf_bytes=pdf_bytes,
                    model_list=[],  # Use default models
                    image_writer=reader_writer,
                    is_debug=False
                )
                
                # Execute the pipeline
                logging.info(f"Executing MinerU conversion pipeline")
                pipe.pipe_classify()
                pipe.pipe_analyze()
                pipe.pipe_parse()
                
                # Get the result
                md_content = pipe.pipe_mk_markdown(
                    image_dir=str(temp_path / "images"),
                    drop_mode="none"  # Keep all content including images
                )
                
                logging.info(f"MinerU conversion complete, writing markdown")
                
                # Write the markdown content to output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    # Add metadata header
                    f.write(f"---\n")
                    f.write(f"source_file: {pdf_path.name}\n")
                    f.write(f"converted_date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"converter: MinerU\n")
                    f.write(f"---\n\n")
                    f.write(f"# {pdf_name}\n\n")
                    f.write(md_content)
                
                logging.info(f"Successfully wrote markdown to: {output_path}")
                
                # If images were extracted, copy them to library/images folder
                images_dir = temp_path / "images"
                if images_dir.exists() and any(images_dir.iterdir()):
                    library_images = output_path.parent / "images" / pdf_name
                    library_images.mkdir(parents=True, exist_ok=True)
                    
                    logging.info(f"Copying extracted images to: {library_images}")
                    for img_file in images_dir.iterdir():
                        if img_file.is_file():
                            shutil.copy2(img_file, library_images / img_file.name)
                    
                    logging.info(f"Extracted {len(list(images_dir.iterdir()))} images")
                
                return output_path
                
            except Exception as e:
                logging.error(f"MinerU processing failed: {e}")
                logging.exception("Full traceback:")
                raise


class PyPDF2Processor(PDFProcessor):
    """
    Alternative PDF processor using PyPDF2 (simple text extraction).
    This is a fallback option for basic text-only PDF extraction.
    """
    
    def check_dependencies(self) -> bool:
        """Check if PyPDF2 is installed"""
        try:
            import PyPDF2
            return True
        except ImportError:
            return False
    
    def get_installation_instructions(self) -> str:
        """Get PyPDF2 installation instructions"""
        return """
PyPDF2 Installation Instructions:
----------------------------------
    pip install PyPDF2
"""
    
    def process_pdf(self, pdf_path: Path, output_path: Path) -> Path:
        """
        Process PDF using PyPDF2 (simple text extraction).
        
        Args:
            pdf_path: Path to the input PDF file
            output_path: Path where the markdown file should be saved
            
        Returns:
            Path to the generated markdown file
        """
        try:
            import PyPDF2
        except ImportError:
            raise ImportError(
                "PyPDF2 is not installed. "
                f"{self.get_installation_instructions()}"
            )
        
        logging.info(f"Processing PDF with PyPDF2: {pdf_path.name}")
        logging.warning("PyPDF2 provides basic text extraction only. Consider using MinerU for better results.")
        
        try:
            # Read PDF and extract text
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)
                logging.info(f"PDF has {num_pages} pages")
                
                text_content = []
                for i, page in enumerate(pdf_reader.pages):
                    logging.debug(f"Extracting text from page {i+1}/{num_pages}")
                    text_content.append(page.extract_text())
            
            # Write markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"---\n")
                f.write(f"source_file: {pdf_path.name}\n")
                f.write(f"converted_date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"converter: PyPDF2\n")
                f.write(f"pages: {num_pages}\n")
                f.write(f"---\n\n")
                f.write(f"# {pdf_path.stem}\n\n")
                f.write("\n\n".join(text_content))
            
            logging.info(f"Successfully wrote markdown to: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"PyPDF2 processing failed: {e}")
            raise


def get_pdf_processor(processor_name: Optional[str] = None) -> PDFProcessor:
    """
    Factory function to get the appropriate PDF processor.
    
    Args:
        processor_name: Name of processor to use ('mineru', 'pypdf2', or None for auto)
        
    Returns:
        PDFProcessor instance
        
    To add a new PDF processor:
    1. Create a new class that inherits from PDFProcessor
    2. Implement all abstract methods
    3. Add it to the processors dict below
    4. Update this docstring with the new processor name
    """
    processors = {
        'mineru': MinerUProcessor,
        'pypdf2': PyPDF2Processor,
    }
    
    # If specific processor requested, try to use it
    if processor_name and processor_name.lower() in processors:
        processor_class = processors[processor_name.lower()]
        processor = processor_class()
        
        if not processor.check_dependencies():
            logging.error(f"Requested processor '{processor_name}' dependencies not found")
            print(processor.get_installation_instructions())
            raise ImportError(f"Dependencies for {processor_name} not installed")
        
        return processor
    
    # Auto-select: try MinerU first, then fall back to PyPDF2
    for name, processor_class in processors.items():
        processor = processor_class()
        if processor.check_dependencies():
            logging.info(f"Using PDF processor: {name}")
            return processor
    
    # No processor available
    logging.error("No PDF processor available")
    print("\nNo PDF processing library found. Please install one of the following:\n")
    for processor_class in processors.values():
        print(processor_class().get_installation_instructions())
    raise ImportError("No PDF processing library available")


def process_file(file_path: str, processor_name: Optional[str] = None) -> Path:
    """
    Process a single PDF file: convert to markdown and save to library/ folder.
    
    Args:
        file_path: Path to the input PDF file
        processor_name: Optional processor name ('mineru', 'pypdf2', or None for auto)
        
    Returns:
        Path to the output markdown file
    """
    file_path = Path(file_path)
    logging.info(f"Starting to process PDF file: {file_path}")
    
    if not file_path.exists():
        logging.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Log file details
    file_size = file_path.stat().st_size
    logging.info(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    
    # Verify it's a PDF file
    if file_path.suffix.lower() != '.pdf':
        logging.error(f"Not a PDF file: {file_path}")
        raise ValueError(f"File must be a PDF, got: {file_path.suffix}")
    
    # Create library directory in the same folder as the script
    script_dir = Path(__file__).parent
    library_path = script_dir / 'library'
    if not library_path.exists():
        logging.info(f"Creating library directory: {library_path}")
        library_path.mkdir(exist_ok=True)
    
    # Determine output filename
    output_filename = file_path.stem + '.md'
    output_path = library_path / output_filename
    logging.info(f"Output file will be: {output_path}")
    
    # Check if output file already exists
    if output_path.exists():
        logging.info(f"Output file already exists, will be overwritten: {output_path}")
    
    # Get PDF processor and process the file
    processor = get_pdf_processor(processor_name)
    processor.process_pdf(file_path, output_path)
    
    logging.info(f"Successfully converted PDF: {file_path.name} -> library/{output_filename}")
    print(f"Converted PDF: {file_path.name} -> library/{output_filename}")
    
    return output_path


def main():
    """Main entry point when script is called directly"""
    logging.info("=" * 60)
    logging.info("PDF Handler Started")
    logging.info("=" * 60)
    
    if len(sys.argv) < 2:
        logging.error("No file path provided as argument")
        print("Usage: python pdf_handler.py <pdf_file_path> [processor_name]", file=sys.stderr)
        print("  processor_name: 'mineru' (default) or 'pypdf2'", file=sys.stderr)
        sys.exit(1)
    
    file_path = sys.argv[1]
    processor_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    logging.info(f"Received file path argument: {file_path}")
    if processor_name:
        logging.info(f"Requested processor: {processor_name}")
    
    try:
        output_path = process_file(file_path, processor_name)
        
        logging.info("=" * 60)
        logging.info("PDF Handler Completed Successfully")
        logging.info("=" * 60)
        sys.exit(0)
    except Exception as e:
        logging.error("=" * 60)
        logging.error(f"PDF Handler Failed: {e}")
        logging.error("=" * 60)
        logging.exception("Full traceback:")
        print(f"Error processing file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
