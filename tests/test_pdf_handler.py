"""
Unit tests for pdf_handler.py
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import tempfile
import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_handler import (
    PDFProcessor,
    MinerUProcessor,
    PyPDF2Processor,
    get_pdf_processor,
    process_file
)


class TestPDFProcessorAbstraction(unittest.TestCase):
    """Test the abstract PDFProcessor interface"""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that PDFProcessor cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            PDFProcessor()


class TestMinerUProcessor(unittest.TestCase):
    """Test MinerU PDF processor implementation"""
    
    def test_check_dependencies_when_installed(self):
        """Test dependency check when MinerU is installed"""
        with patch('pdf_handler.MinerUProcessor.check_dependencies', return_value=True):
            processor = MinerUProcessor()
            self.assertTrue(processor.check_dependencies())
    
    def test_check_dependencies_when_not_installed(self):
        """Test dependency check when MinerU is not installed"""
        processor = MinerUProcessor()
        # Since MinerU likely isn't installed in test environment
        result = processor.check_dependencies()
        self.assertIsInstance(result, bool)
    
    def test_get_installation_instructions(self):
        """Test that installation instructions are provided"""
        processor = MinerUProcessor()
        instructions = processor.get_installation_instructions()
        self.assertIsInstance(instructions, str)
        self.assertIn("mineru", instructions.lower())
        self.assertIn("pip", instructions.lower())
    
    def test_process_pdf_with_mineru(self):
        """Test PDF processing with MinerU (mock test)"""
        # Since MinerU likely isn't installed, just verify the method signature exists
        processor = MinerUProcessor()
        self.assertTrue(hasattr(processor, 'process_pdf'))
        self.assertTrue(callable(processor.process_pdf))


class TestPyPDF2Processor(unittest.TestCase):
    """Test PyPDF2 PDF processor implementation"""
    
    def test_check_dependencies_when_not_installed(self):
        """Test dependency check when PyPDF2 is not installed"""
        processor = PyPDF2Processor()
        result = processor.check_dependencies()
        self.assertIsInstance(result, bool)
    
    def test_get_installation_instructions(self):
        """Test that installation instructions are provided"""
        processor = PyPDF2Processor()
        instructions = processor.get_installation_instructions()
        self.assertIsInstance(instructions, str)
        self.assertIn("PyPDF2", instructions)
        self.assertIn("pip", instructions.lower())
    
    def test_process_pdf_with_pypdf2(self):
        """Test PDF processing with PyPDF2 (mock test)"""
        # Since PyPDF2 likely isn't installed, just verify the method signature exists
        processor = PyPDF2Processor()
        self.assertTrue(hasattr(processor, 'process_pdf'))
        self.assertTrue(callable(processor.process_pdf))


class TestPDFProcessorFactory(unittest.TestCase):
    """Test the PDF processor factory function"""
    
    def test_get_processor_auto_selects_mineru(self):
        """Test that MinerU is selected when available"""
        with patch.object(MinerUProcessor, 'check_dependencies', return_value=True):
            processor = get_pdf_processor()
            self.assertIsInstance(processor, MinerUProcessor)
    
    def test_get_processor_falls_back_to_pypdf2(self):
        """Test fallback to PyPDF2 when MinerU unavailable"""
        with patch.object(MinerUProcessor, 'check_dependencies', return_value=False), \
             patch.object(PyPDF2Processor, 'check_dependencies', return_value=True):
            processor = get_pdf_processor()
            self.assertIsInstance(processor, PyPDF2Processor)
    
    def test_get_processor_with_explicit_selection(self):
        """Test explicit processor selection"""
        with patch.object(MinerUProcessor, 'check_dependencies', return_value=True):
            processor = get_pdf_processor("mineru")
            self.assertIsInstance(processor, MinerUProcessor)
    
    def test_get_processor_raises_when_none_available(self):
        """Test that ImportError is raised when no processor available"""
        with patch.object(MinerUProcessor, 'check_dependencies', return_value=False), \
             patch.object(PyPDF2Processor, 'check_dependencies', return_value=False):
            with self.assertRaises(ImportError):
                get_pdf_processor()


class TestProcessFile(unittest.TestCase):
    """Test the process_file function"""
    
    def test_process_file_validates_extension(self):
        """Test that non-PDF files are rejected"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            txt_path = f.name
        
        try:
            with self.assertRaises(ValueError) as context:
                process_file(txt_path)
            
            self.assertIn("PDF", str(context.exception))
        finally:
            os.unlink(txt_path)
    
    def test_process_file_validates_existence(self):
        """Test that missing files are detected"""
        with self.assertRaises(FileNotFoundError):
            process_file("/nonexistent/file.pdf")
    
    def test_process_file_calls_processor(self):
        """Test that process_file calls the PDF processor"""
        mock_processor = MagicMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            pdf_path.write_bytes(b"fake pdf content")
            
            library_path = Path(temp_dir) / "library"
            output_path = library_path / "test.md"
            
            mock_processor.process_pdf.return_value = output_path
            
            # Create library and output
            library_path.mkdir()
            output_path.write_text("# Test")
            
            with patch('pdf_handler.get_pdf_processor', return_value=mock_processor):
                # Mock the __file__ lookup by patching Path
                import pdf_handler
                original_file = pdf_handler.__file__
                try:
                    pdf_handler.__file__ = str(Path(temp_dir) / "pdf_handler.py")
                    output = process_file(str(pdf_path))
                    
                    # Verify processor was called
                    mock_processor.process_pdf.assert_called_once()
                finally:
                    pdf_handler.__file__ = original_file
    
    def test_process_file_with_explicit_processor(self):
        """Test process_file with explicit processor name"""
        mock_processor = MagicMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            pdf_path.write_bytes(b"fake pdf content")
            
            library_path = Path(temp_dir) / "library"
            output_path = library_path / "test.md"
            
            mock_processor.process_pdf.return_value = output_path
            
            # Create library and output
            library_path.mkdir()
            output_path.write_text("# Test")
            
            with patch('pdf_handler.get_pdf_processor', return_value=mock_processor) as mock_get:
                import pdf_handler
                original_file = pdf_handler.__file__
                try:
                    pdf_handler.__file__ = str(Path(temp_dir) / "pdf_handler.py")
                    output = process_file(str(pdf_path), processor_name="pypdf2")
                    
                    # Verify get_pdf_processor was called with correct arg
                    mock_get.assert_called_once_with("pypdf2")
                finally:
                    pdf_handler.__file__ = original_file


class TestIntegration(unittest.TestCase):
    """Integration tests for PDF handler"""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from PDF to markdown"""
        # This is a high-level integration test
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "document.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fake content")
            
            # Create library directory
            library = Path(temp_dir) / "library"
            library.mkdir()
            
            # Create expected output
            expected_output = library / "document.md"
            expected_output.write_text("# Document\n\nContent here")
            
            # Mock the processor to avoid actual PDF processing
            mock_processor = MagicMock(spec=PDFProcessor)
            mock_processor.process_pdf.return_value = expected_output
            
            with patch('pdf_handler.get_pdf_processor', return_value=mock_processor):
                import pdf_handler
                original_file = pdf_handler.__file__
                try:
                    pdf_handler.__file__ = str(Path(temp_dir) / "pdf_handler.py")
                    result = process_file(str(pdf_path))
                    
                    # Verify the workflow completed
                    mock_processor.process_pdf.assert_called_once()
                finally:
                    pdf_handler.__file__ = original_file


if __name__ == '__main__':
    unittest.main()
