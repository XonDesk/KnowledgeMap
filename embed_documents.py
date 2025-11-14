"""
Neo4j Document Embedding Script
Processes markdown documents, generates embeddings using pluggable models,
and stores them in Neo4j with vector indexing.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import os
import sys
import subprocess
from pathlib import Path
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import re


class EmbeddingModel(ABC):
    """Abstract base class for embedding models"""
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimension of the embedding"""
        pass


class Qwen3Embedding(EmbeddingModel):
    """Qwen3 embedding model wrapper using sentence-transformers"""
    
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            model_name = "Qwen/Qwen3-Embedding-0.6B"
            dimension = 896
            
            print(f"Loading Qwen3 model: {model_name}...")
            
            # Load the model
            self.model = SentenceTransformer(model_name)
            
            self._dimension = dimension
            self.torch = torch
            print(f"Qwen3 model loaded successfully")
            
        except ImportError:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers")
    
    def embed(self, text: str, is_query: bool = False) -> List[float]:
        """Generate embedding for text
        
        Args:
            text: Input text
            is_query: If True, uses the 'query' prompt for better retrieval
        """
        with self.torch.no_grad():
            if is_query:
                # Use the built-in "query" prompt for queries
                embedding = self.model.encode(text, prompt_name="query")
            else:
                # No prompt for documents
                embedding = self.model.encode(text)
        
        return embedding.tolist()
    
    def get_dimension(self) -> int:
        return self._dimension


class OpenAIEmbedding(EmbeddingModel):
    """OpenAI embedding model wrapper"""
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model_name = model_name
            self._dimension = 1536 if "3-small" in model_name else 3072
        except ImportError:
            raise ImportError("Install openai: pip install openai")
    
    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=text,
            model=self.model_name
        )
        return response.data[0].embedding
    
    def get_dimension(self) -> int:
        return self._dimension


class HuggingFaceEmbedding(EmbeddingModel):
    """HuggingFace sentence-transformers wrapper"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers")
    
    def embed(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def get_dimension(self) -> int:
        return self._dimension


class CohereEmbedding(EmbeddingModel):
    """Cohere embedding model wrapper"""
    
    def __init__(self, model_name: str = "embed-english-v3.0"):
        try:
            import cohere
            self.client = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))
            self.model_name = model_name
            self._dimension = 1024
        except ImportError:
            raise ImportError("Install cohere: pip install cohere")
    
    def embed(self, text: str) -> List[float]:
        response = self.client.embed(
            texts=[text],
            model=self.model_name,
            input_type="search_document"
        )
        return response.embeddings[0]
    
    def get_dimension(self) -> int:
        return self._dimension


def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


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
        print(f"Neo4j connection failed: {e}")
        return False




class DocumentEmbedder:
    """Handles markdown document embedding and Neo4j storage"""
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        embedding_model: EmbeddingModel,
        index_name: str = "document_embeddings"
    ):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_model = embedding_model
        self.index_name = index_name
        self.embedding_dim = embedding_model.get_dimension()
    
    def close(self):
        """Close Neo4j driver connection"""
        self.driver.close()
    
    def create_vector_index(self):
        """Create vector index on Document nodes"""
        with self.driver.session() as session:
            # Check if index exists
            result = session.run("SHOW INDEXES")
            existing_indexes = [record["name"] for record in result]
            
            if self.index_name not in existing_indexes:
                session.run(f"""
                    CREATE VECTOR INDEX {self.index_name} IF NOT EXISTS
                    FOR (d:Document)
                    ON d.embedding
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {self.embedding_dim},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                """)
                print(f"Vector index '{self.index_name}' created successfully")
            else:
                print(f"Vector index '{self.index_name}' already exists")
    
    def parse_markdown_metadata(self, markdown_text: str) -> tuple[str, Dict[str, str]]:
        """
        Parse markdown frontmatter and return content + metadata
        
        Args:
            markdown_text: Raw markdown text
        
        Returns:
            Tuple of (content, metadata_dict)
        """
        metadata = {}
        content = markdown_text
        
        # Check for YAML frontmatter
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, markdown_text, re.DOTALL)
        
        if match:
            frontmatter = match.group(1)
            content = markdown_text[match.end():]
            
            # Parse simple YAML key-value pairs
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip().strip('"').strip("'")
        
        return content, metadata
    
    def process_markdown_file(
        self,
        file_path: str,
        doc_id: Optional[str] = None,
        additional_metadata: Optional[dict] = None
    ) -> str:
        """
        Process a markdown file: read, parse, embed, and store
        
        Args:
            file_path: Path to markdown file
            doc_id: Optional document ID (defaults to filename without extension)
            additional_metadata: Optional additional metadata dictionary
        
        Returns:
            Document ID
        """
        if not file_path.endswith('.md'):
            raise ValueError("File must be a markdown file (.md)")
        
        if doc_id is None:
            doc_id = os.path.splitext(os.path.basename(file_path))[0]
        
        # Read markdown file
        with open(file_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        # Parse frontmatter and content
        content, frontmatter_metadata = self.parse_markdown_metadata(markdown_text)
        
        # Combine metadata
        metadata = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_type': 'markdown',
            **frontmatter_metadata
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        # Generate embedding
        print(f"Generating embedding for document: {doc_id}")
        embedding = self.embedding_model.embed(content)
        
        # Store in Neo4j
        with self.driver.session() as session:
            query = """
            MERGE (d:Document {id: $doc_id})
            SET d.text = $text,
                d.embedding = $embedding,
                d.updated_at = datetime()
            """
            
            params = {
                "doc_id": doc_id,
                "text": content,
                "embedding": embedding
            }
            
            # Add metadata if provided
            for key, value in metadata.items():
                # Sanitize key for Cypher
                safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', key)
                query += f"\nSET d.{safe_key} = ${safe_key}"
                params[safe_key] = value
            
            query += "\nRETURN d.id as doc_id"
            
            result = session.run(query, params)
            record = result.single()
            print(f"Document stored: {record['doc_id']}")
            
            return record["doc_id"]
    
    def search_similar_documents(
        self,
        query_text: str,
        top_k: int = 5
    ) -> List[dict]:
        """
        Search for similar documents using vector similarity
        
        Args:
            query_text: Query text
            top_k: Number of results to return
        
        Returns:
            List of similar documents with scores
        """
        # For Qwen3, use is_query=True to add instruction
        if isinstance(self.embedding_model, Qwen3Embedding):
            query_embedding = self.embedding_model.embed(query_text, is_query=True)
        else:
            query_embedding = self.embedding_model.embed(query_text)
        
        with self.driver.session() as session:
            result = session.run(f"""
                CALL db.index.vector.queryNodes(
                    '{self.index_name}',
                    $top_k,
                    $query_embedding
                )
                YIELD node, score
                RETURN node.id as doc_id,
                       node.text as text,
                       node.file_name as file_name,
                       score
                ORDER BY score DESC
            """, {
                "top_k": top_k,
                "query_embedding": query_embedding
            })
            
            return [dict(record) for record in result]


def get_embedding_model_from_config(model_id: Optional[str] = None) -> EmbeddingModel:
    """
    Get embedding model from configuration string
    
    Args:
        model_id: Model identifier from .env file (e.g., "qwen3", "huggingface:all-MiniLM-L6-v2")
    
    Returns:
        Initialized EmbeddingModel instance
    """
    if model_id is None:
        model_id = os.getenv("EMBEDDING_MODEL", "qwen3")
    
    try:
        if model_id == "qwen3":
            return Qwen3Embedding()
        elif model_id.startswith("huggingface:"):
            model_name = model_id.split(":", 1)[1]
            return HuggingFaceEmbedding(model_name)
        elif model_id.startswith("openai:"):
            model_name = model_id.split(":", 1)[1]
            return OpenAIEmbedding(model_name)
        elif model_id.startswith("cohere:"):
            model_name = model_id.split(":", 1)[1]
            return CohereEmbedding(model_name)
        else:
            print(f"Unknown model ID: {model_id}")
            print("Falling back to Qwen3")
            return Qwen3Embedding()
    except Exception as e:
        print(f"Error initializing model '{model_id}': {e}")
        print("Please check your configuration or run file_dispatcher.py to reconfigure.")
        sys.exit(1)


def process_markdown_document(
    markdown_file_path: str,
    embedding_model: Optional[EmbeddingModel] = None,
    neo4j_uri: Optional[str] = None,
    neo4j_user: Optional[str] = None,
    neo4j_password: Optional[str] = None,
    doc_id: Optional[str] = None
) -> str:
    """
    Main function to process a markdown document
    
    Args:
        markdown_file_path: Path to markdown file
        embedding_model: Optional pre-initialized embedding model
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        doc_id: Optional document ID
    
    Returns:
        Document ID
    """
    # Load environment variables
    load_env_file()
    
    # Get embedding model if not provided
    if embedding_model is None:
        embedding_model = get_embedding_model_from_config()
    
    # Get Neo4j connection details
    if neo4j_uri is None:
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    if neo4j_user is None:
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    if neo4j_password is None:
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if not neo4j_password or neo4j_password.strip() == "":
            neo4j_password = input("Enter Neo4j password: ")
    
    # Test Neo4j connection
    print(f"Testing Neo4j connection to {neo4j_uri}...")
    if not test_neo4j_connection(neo4j_uri, neo4j_user, neo4j_password):
        print("\nNeo4j connection failed.")
        print("Please ensure Neo4j is running and credentials are configured.")
        print("Run the file_dispatcher.py script to set up Neo4j, or configure manually.")
        sys.exit(1)
    
    print("Neo4j connection successful!")
    
    # Initialize embedder
    embedder = DocumentEmbedder(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        embedding_model=embedding_model,
        index_name="document_embeddings"
    )
    
    try:
        # Create vector index
        embedder.create_vector_index()
        
        # Process markdown file
        doc_id = embedder.process_markdown_file(markdown_file_path, doc_id=doc_id)
        
        return doc_id
    
    finally:
        embedder.close()


def main():
    """CLI entry point"""
    
    if len(sys.argv) < 2:
        print("Usage: python embed_documents.py <markdown_file_path> [doc_id]")
        sys.exit(1)
    
    markdown_file_path = sys.argv[1]
    doc_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(markdown_file_path):
        print(f"Error: File not found: {markdown_file_path}")
        sys.exit(1)
    
    try:
        result_doc_id = process_markdown_document(markdown_file_path, doc_id=doc_id)
        print(f"\n[SUCCESS] Successfully processed document: {result_doc_id}")
    except Exception as e:
        print(f"\n[ERROR] Error processing document: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
