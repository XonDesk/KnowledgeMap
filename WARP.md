# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

KnowledgeMap is a document ingestion pipeline that processes various file formats (text, audio, PDFs), converts them to markdown, generates embeddings, and stores them in Neo4j for semantic search. The system uses a dispatcher pattern to route files to specialized handlers.

## Core Architecture

### Orchestration Pattern
The codebase follows a **dispatcher-handler** architecture:

1. **file_dispatcher.py** (Main orchestrator)
   - Entry point for processing documents
   - Routes files to specialized handlers based on file extension
   - Manages Neo4j connection validation and setup
   - Handles embedding model configuration
   - Coordinates the embedding pipeline after file processing

2. **Handler Scripts** (Format-specific processors)
   - `text_handler.py` - Processes .txt, .md, .markdown, .doc, .docx files
   - `audio_handler.py` - Processes audio/video files (.mp3, .wav, .mp4, etc.) using WhisperX with speaker diarization
   - `pdf_handler.py` - (Referenced but not present in codebase)
   
   All handlers convert input to markdown format and save to `library/` folder.

3. **embed_documents.py** (Embedding pipeline)
   - Generates vector embeddings for markdown documents
   - Supports pluggable embedding models (Qwen3, OpenAI, HuggingFace, Cohere)
   - Stores embeddings in Neo4j with vector indexing
   - Parses markdown frontmatter for metadata

4. **setup_neo4j.py** (Configuration utility)
   - Interactive wizard for Neo4j connection setup
   - Tests database connectivity
   - Manages `.env` file creation/updates

### Data Flow
```
Input Files → file_dispatcher.py
  ↓
Handler Selection (based on extension)
  ↓
text_handler.py / audio_handler.py / pdf_handler.py
  ↓
Markdown files in library/
  ↓
embed_documents.py (batch processing)
  ↓
Neo4j Database (with vector embeddings)
```

### Environment Configuration
Configuration is stored in `.env` file with these key variables:
- `EMBEDDING_MODEL` - Model identifier (e.g., "qwen3", "huggingface:all-MiniLM-L6-v2")
- `NEO4J_URI` - Neo4j connection string (default: bolt://localhost:7687)
- `NEO4J_USER` - Neo4j username (default: neo4j)
- `NEO4J_PASSWORD` - Neo4j password
- `HUGGINGFACE_TOKEN` - Required for audio transcription diarization

## Development Commands

### Processing Documents

Process a folder of documents:
```powershell
python file_dispatcher.py "D:\path\to\folder" --log
```

Process recursively with debug logging:
```powershell
python file_dispatcher.py "D:\path\to\folder" --recursive --log --log-level DEBUG
```

Dry run (preview what would be executed):
```powershell
python file_dispatcher.py "D:\path\to\folder" --dry-run --log
```

### Direct Handler Execution

Process a single text file:
```powershell
python text_handler.py "D:\path\to\file.txt"
```

Process a single audio file:
```powershell
python audio_handler.py "D:\path\to\audio.mp3"
```

### Embedding Operations

Embed a single markdown document:
```powershell
python embed_documents.py "library\document.md"
```

Embed with custom document ID:
```powershell
python embed_documents.py "library\document.md" "custom_doc_id"
```

### Setup and Configuration

Run Neo4j setup wizard:
```powershell
python setup_neo4j.py
```

### Debugging in VSCode

The `.vscode\launch.json` is configured to debug the current file with test arguments:
- File: `${file}` (current open file)
- Arguments: `["D:\\code\\test", "--log"]`

## Key Implementation Details

### Embedding Model System
The embedding system uses an abstract base class (`EmbeddingModel`) with concrete implementations:
- `Qwen3Embedding` - Uses sentence-transformers with Qwen/Qwen3-Embedding-0.6B (896 dimensions)
- `HuggingFaceEmbedding` - Generic sentence-transformers wrapper
- `OpenAIEmbedding` - OpenAI API client (1536 or 3072 dimensions)
- `CohereEmbedding` - Cohere API client (1024 dimensions)

When adding a new model, extend `EmbeddingModel` and update `get_embedding_model_from_config()` in `embed_documents.py`.

### Duplicate Detection
The dispatcher checks the `library/` folder for files with matching stems (filename without extension) before processing. Users are prompted to choose whether to reprocess duplicates.

### Audio Transcription Pipeline
Audio processing uses WhisperX with 4 stages:
1. Transcription (large-v2 model)
2. Alignment (language-specific)
3. Diarization (speaker identification)
4. Markdown generation

Requires CUDA for optimal performance but falls back to CPU with int8 quantization.

### Neo4j Vector Index
Documents are stored with properties:
- `id` - Document identifier (defaults to filename stem)
- `text` - Document content
- `embedding` - Vector embedding array
- `file_path`, `file_name`, `file_type` - Metadata
- Custom metadata from markdown frontmatter

Vector index uses cosine similarity for semantic search.

## Python Dependencies

Key dependencies (install as needed):
- `neo4j` - Neo4j database driver
- `sentence-transformers` - For Qwen3 and HuggingFace embeddings
- `torch` - PyTorch for embedding models
- `python-docx` - Word document processing
- `whisperx` - Audio transcription with diarization
- `openai` - OpenAI API client (optional)
- `cohere` - Cohere API client (optional)

## Important Notes

- The `.env` file contains sensitive credentials and should not be committed to version control
- Audio processing requires a HuggingFace token for speaker diarization
- The system automatically creates the `library/` folder if it doesn't exist
- All handlers output to markdown format, ensuring consistent input for embedding
- Embedding dimensions must match the configured model in Neo4j vector index
- The dispatcher runs embedding as a batch operation after all files are processed
