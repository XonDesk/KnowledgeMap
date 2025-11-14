#!/usr/bin/env python3
"""
Scan a folder and automatically dispatch files to handler scripts based on type.

The script looks for these handler scripts in the same directory:
- text_handler.py    → for .txt, .md, .markdown, .doc, .docx
- pdf_handler.py     → for .pdf
- audio_handler.py   → for .mp3, .wav, .flac, .m4a, .ogg, .opus, .wma, .aac, .mp4, .mkv, .avi, .mov, .webm

Usage:
  python file_dispatcher.py "C:\\path\\to\\folder" --recursive --log --log-level DEBUG
  python file_dispatcher.py "D:\\documents" --log
"""
import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# File type mappings
TEXT_EXTS = {".txt", ".md", ".markdown", ".doc", ".docx"}
PDF_EXTS = {".pdf"}
# WhisperX supported audio formats
AUDIO_EXTS = {
    ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".wma", ".aac",
    ".mp4", ".mkv", ".avi", ".mov", ".webm"
}

HANDLER_MAP = {
    "text": "text_handler.py",
    "pdf": "pdf_handler.py",
    "audio": "audio_handler.py",
}


def test_neo4j_connection(uri: str, user: str, password: str) -> bool:
    """
    Test Neo4j connection
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except (ServiceUnavailable, AuthError, Exception) as e:
        logging.debug(f"Neo4j connection failed: {e}")
        return False


def load_env_file(env_path: Path) -> None:
    """Load environment variables from .env file"""
    if env_path.exists():
        logging.debug(f"Loading environment variables from: {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


def update_env_file(env_path: Path, key: str, value: str) -> bool:
    """Update or add a key-value pair in the .env file"""
    try:
        # Read existing .env if it exists
        existing_env = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        existing_env[k.strip()] = v.strip()
        
        # Update with new value
        existing_env[key] = value
        
        # Write back to .env
        with open(env_path, 'w') as f:
            for k, v in existing_env.items():
                f.write(f"{k}={v}\n")
        
        logging.debug(f"Updated .env file with {key}")
        return True
    
    except Exception as e:
        logging.error(f"Error updating .env file: {e}")
        return False


def get_embedding_model_choice() -> str:
    """
    Prompt user to select an embedding model
    
    Returns:
        Model identifier string to be saved in .env
    """
    print("\n" + "="*60)
    print("Select Embedding Model")
    print("="*60)
    print("1. Qwen3 - 0.6B (Local, Free, Recommended)")
    print("2. HuggingFace - all-MiniLM-L6-v2 (Local, Free, Fast)")
    print("3. HuggingFace - all-mpnet-base-v2 (Local, Free, Better Quality)")
    print("4. OpenAI - text-embedding-3-small (API, Paid)")
    print("5. OpenAI - text-embedding-3-large (API, Paid)")
    print("6. Cohere - embed-english-v3.0 (API, Paid)")
    print("="*60)
    
    model_map = {
        "1": "qwen3",
        "2": "huggingface:all-MiniLM-L6-v2",
        "3": "huggingface:all-mpnet-base-v2",
        "4": "openai:text-embedding-3-small",
        "5": "openai:text-embedding-3-large",
        "6": "cohere:embed-english-v3.0"
    }
    
    while True:
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice in model_map:
            return model_map[choice]
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")


def get_model_display_name(model_id: str) -> str:
    """Convert model ID to display name"""
    model_names = {
        "qwen3": "Qwen3 - 0.6B",
        "huggingface:all-MiniLM-L6-v2": "HuggingFace - all-MiniLM-L6-v2",
        "huggingface:all-mpnet-base-v2": "HuggingFace - all-mpnet-base-v2",
        "openai:text-embedding-3-small": "OpenAI - text-embedding-3-small",
        "openai:text-embedding-3-large": "OpenAI - text-embedding-3-large",
        "cohere:embed-english-v3.0": "Cohere - embed-english-v3.0"
    }
    return model_names.get(model_id, model_id)


def run_neo4j_setup():
    """
    Call the Neo4j setup handler script
    """
    setup_script = os.path.join(os.path.dirname(__file__), "setup_neo4j.py")
    
    if not os.path.exists(setup_script):
        print(f"\nError: Neo4j setup script not found at: {setup_script}")
        print("Please create a setup_neo4j.py script or configure Neo4j manually.")
        print("\nRequired environment variables:")
        print("  - NEO4J_URI (default: bolt://localhost:7687)")
        print("  - NEO4J_USER (default: neo4j)")
        print("  - NEO4J_PASSWORD")
        return False
    
    print(f"\nRunning Neo4j setup script: {setup_script}")
    try:
        result = subprocess.run([sys.executable, setup_script], check=True)
        if result.returncode == 0:
            print("Neo4j setup completed successfully")
            return True
    except subprocess.CalledProcessError as e:
        print(f"Setup script failed with error: {e}")
        return False
    except Exception as e:
        print(f"Error running setup script: {e}")
        return False
    
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan folder and dispatch files to handler scripts automatically.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folder",
        type=str,
        help="Folder path to scan for files",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Scan subfolders recursively",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Enable logging output",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (only used if --log is enabled)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without actually running handlers",
    )
    return parser.parse_args()


def setup_logging(enabled: bool, level: str) -> None:
    """Configure logging based on user preferences."""
    if enabled:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Disable all logging
        logging.disable(logging.CRITICAL)


def get_file_category(file_path: Path) -> Optional[str]:
    """Determine category based on file extension."""
    ext = file_path.suffix.lower()
    if ext in TEXT_EXTS:
        return "text"
    elif ext in PDF_EXTS:
        return "pdf"
    elif ext in AUDIO_EXTS:
        return "audio"
    return None


def find_handler_script(category: str, script_dir: Path) -> Optional[Path]:
    """Locate the handler script for a given category."""
    handler_name = HANDLER_MAP.get(category)
    if not handler_name:
        return None
    
    handler_path = script_dir / handler_name
    if handler_path.exists() and handler_path.is_file():
        return handler_path
    
    return None


def collect_files(folder: Path, recursive: bool) -> List[Path]:
    """Collect all files from the folder."""
    files = []
    try:
        if recursive:
            for item in folder.rglob("*"):
                if item.is_file():
                    files.append(item)
        else:
            for item in folder.iterdir():
                if item.is_file():
                    files.append(item)
    except PermissionError as e:
        logging.error(f"Permission denied accessing: {e}")
    
    return files


def check_library_for_duplicate(file_path: Path, library_folder: Path) -> bool:
    """
    Check if a file with the same name (excluding extension) exists in the library folder.
    
    Returns: True if duplicate found, False otherwise
    """
    file_stem = file_path.stem  # filename without extension
    
    # Search library folder for files with matching stem
    for lib_file in library_folder.iterdir():
        if lib_file.is_file() and lib_file.stem == file_stem:
            return True
    
    return False


def dispatch_file(
    file_path: Path,
    handlers: Dict[str, Optional[Path]],
    dry_run: bool,
    skip_set: Set[Path],
) -> Tuple[str, bool, Optional[str]]:
    """
    Dispatch a file to its handler.
    
    Returns: (status, success, error_msg)
      - status: "dispatched", "skipped", "no_handler", "error", "duplicate"
      - success: True if handled successfully
      - error_msg: Error description if any
    """
    category = get_file_category(file_path)
    
    if not category:
        logging.debug(f"Skipping unsupported file: {file_path}")
        return ("skipped", True, None)
    
    # Check if file should be skipped due to user decision
    if file_path in skip_set:
        logging.info(f"Skipping duplicate (user decision): {file_path.name}")
        return ("duplicate", True, None)
    
    handler = handlers.get(category)
    if not handler:
        logging.warning(f"No handler found for {category} file: {file_path}")
        return ("no_handler", False, f"Missing {HANDLER_MAP[category]}")
    
    cmd = [sys.executable, str(handler), str(file_path.resolve())]
    logging.info(f"[{category.upper()}] Processing: {file_path.name}")
    logging.debug(f"Command: {' '.join(cmd)}")
    
    if dry_run:
        print(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        return ("dispatched", True, None)
    
    try:
        result = subprocess.run(
            cmd,
            check=False,
        )
        
        if result.returncode == 0:
            logging.debug(f"Successfully processed: {file_path.name}")
            return ("dispatched", True, None)
        else:
            logging.error(
                f"Handler failed for {file_path.name} (exit code {result.returncode})"
            )
            return ("error", False, f"Exit code {result.returncode}")
            
    except Exception as e:
        logging.exception(f"Exception while processing {file_path.name}")
        return ("error", False, str(e))


def main() -> int:
    args = parse_args()
    
    # Setup logging
    setup_logging(args.log, args.log_level)
    
    # Validate folder
    folder = Path(args.folder)
    if not folder.exists():
        print(f"Error: Folder does not exist: {folder}", file=sys.stderr)
        return 1
    if not folder.is_dir():
        print(f"Error: Path is not a directory: {folder}", file=sys.stderr)
        return 1
    
    # Check for library folder, create if it doesn't exist
    script_dir = Path(__file__).parent
    library_folder = script_dir / "library"
    if not library_folder.exists():
        logging.info(f"Creating library folder: {library_folder}")
        library_folder.mkdir(parents=True, exist_ok=True)
    else:
        logging.info(f"Library folder found: {library_folder}")
    
    # Load environment variables from .env file if it exists
    env_path = script_dir / ".env"
    load_env_file(env_path)
    
    # Check for embedding model configuration
    embedding_model = os.getenv("EMBEDDING_MODEL")
    if not embedding_model or embedding_model.strip() == "":
        print("\n" + "="*60)
        print("INITIAL SETUP: Embedding Model Configuration")
        print("="*60)
        print("No embedding model found in configuration.")
        embedding_model = get_embedding_model_choice()
        update_env_file(env_path, "EMBEDDING_MODEL", embedding_model)
        os.environ["EMBEDDING_MODEL"] = embedding_model
        print(f"\n✓ Embedding model saved: {get_model_display_name(embedding_model)}")
    else:
        print(f"\nEmbedding Model: {get_model_display_name(embedding_model)}")
    
    # Check Neo4j connection and run setup if needed
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    # Check if Neo4j credentials are properly configured
    if not neo4j_password or neo4j_password.strip() == "":
        logging.info("NEO4J_PASSWORD not found in .env file")
        neo4j_password = None
    
    logging.info(f"Testing Neo4j connection to {neo4j_uri}...")
    if not test_neo4j_connection(neo4j_uri, neo4j_user, neo4j_password):
        print("\nNeo4j connection failed. Running setup...")
        if not run_neo4j_setup():
            print("\nWarning: Neo4j setup did not complete successfully.")
            print("File processing may fail if handlers require Neo4j.")
            proceed = input("Do you want to continue anyway? (y/n): ").strip().lower()
            if proceed != 'y':
                return 1
        else:
            # Reload environment variables after setup
            load_env_file(env_path)
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            
            if not test_neo4j_connection(neo4j_uri, neo4j_user, neo4j_password):
                print("Neo4j connection still failed after setup.")
                proceed = input("Do you want to continue anyway? (y/n): ").strip().lower()
                if proceed != 'y':
                    return 1
    else:
        logging.info("Neo4j connection successful!")
    
    # Locate handler scripts
    handlers: Dict[str, Optional[Path]] = {}
    
    logging.info(f"Looking for handler scripts in: {script_dir}")
    for category, handler_name in HANDLER_MAP.items():
        handler_path = find_handler_script(category, script_dir)
        handlers[category] = handler_path
        if handler_path:
            logging.info(f"Found {category} handler: {handler_name}")
        else:
            logging.warning(f"Handler not found: {handler_name}")
    
    # Collect files
    logging.info(f"Scanning folder: {folder}")
    files = collect_files(folder, args.recursive)
    logging.info(f"Found {len(files)} total files")
    
    # Check for duplicates in library
    duplicates: List[Path] = []
    for file_path in files:
        category = get_file_category(file_path)
        if category and check_library_for_duplicate(file_path, library_folder):
            duplicates.append(file_path)
    
    # Handle duplicates if found
    skip_set: Set[Path] = set()
    if duplicates:
        print("\n" + "=" * 60)
        print(f"DUPLICATE FILES FOUND: {len(duplicates)}")
        print("=" * 60)
        print("The following files already exist in the library (by name):")
        for dup in duplicates:
            print(f"  - {dup.name}")
        print("=" * 60)
        
        while True:
            response = input("\nDo you want to ingest these duplicate files? (Y/N): ").strip().upper()
            if response in ['Y', 'YES']:
                logging.info("User chose to ingest all duplicates")
                break
            elif response in ['N', 'NO']:
                logging.info("User chose to skip all duplicates")
                skip_set = set(duplicates)
                break
            else:
                print("Please enter Y or N.")
    
    # Process files
    stats = {
        "total": len(files),
        "dispatched": 0,
        "skipped": 0,
        "no_handler": 0,
        "errors": 0,
        "duplicates_skipped": 0,
    }
    
    processed_files: List[Path] = []  # Track successfully processed files
    
    for file_path in files:
        status, success, error = dispatch_file(file_path, handlers, args.dry_run, skip_set)
        
        if status == "dispatched":
            stats["dispatched"] += 1
            # Track the output file in library for embedding
            output_file = library_folder / (file_path.stem + '.md')
            if output_file.exists():
                processed_files.append(output_file)
        elif status == "skipped":
            stats["skipped"] += 1
        elif status == "no_handler":
            stats["no_handler"] += 1
        elif status == "error":
            stats["errors"] += 1
        elif status == "duplicate":
            stats["duplicates_skipped"] += 1
    
    # Run embedding for all processed files
    if processed_files and not args.dry_run:
        embed_script = script_dir / 'embed_documents.py'
        
        if embed_script.exists():
            print("\n" + "=" * 60)
            print(f"EMBEDDING {len(processed_files)} DOCUMENTS")
            print("=" * 60)
            logging.info(f"Starting batch embedding for {len(processed_files)} documents")
            
            for doc_path in processed_files:
                logging.info(f"Embedding: {doc_path.name}")
                print(f"Embedding: {doc_path.name}")
                
                try:
                    result = subprocess.run(
                        [sys.executable, str(embed_script), str(doc_path)],
                        capture_output=True,
                        text=True,
                        env=os.environ.copy()
                    )
                    
                    if result.returncode != 0:
                        logging.warning(f"Embedding failed for {doc_path.name} with exit code {result.returncode}")
                        print(f"Warning: Embedding failed for {doc_path.name}")
                        if result.stderr:
                            logging.error(f"Error output: {result.stderr}")
                    else:
                        logging.info(f"Successfully embedded: {doc_path.name}")
                except Exception as e:
                    logging.error(f"Exception while embedding {doc_path.name}: {e}")
                    print(f"Error embedding {doc_path.name}: {e}")
            
            print("=" * 60)
            print("EMBEDDING COMPLETE")
            print("=" * 60)
        else:
            logging.warning(f"embed_documents.py not found at {embed_script}")
            print(f"\nWarning: embed_documents.py not found, skipping embedding phase")
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total files found:        {stats['total']}")
    print(f"Successfully dispatched:  {stats['dispatched']}")
    print(f"Skipped (unsupported):    {stats['skipped']}")
    print(f"Duplicates skipped:       {stats['duplicates_skipped']}")
    print(f"No handler available:     {stats['no_handler']}")
    print(f"Errors:                   {stats['errors']}")
    print("=" * 60)
    
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
