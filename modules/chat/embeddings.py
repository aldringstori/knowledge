# File: ./modules/chat/embeddings.py
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import torch
from utils.logging_setup import logger

# Global manager instance
_manager = None

def get_manager():
    """Get or create global embeddings manager"""
    global _manager
    if _manager is None:
        _manager = EmbeddingsManager()
    return _manager

class EmbeddingsManager:
    def __init__(self):
        self.model = None
        # Changed model to match the 384 dimensions in Qdrant configuration
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions

    def initialize_model(self) -> bool:
        """Initialize the embeddings model"""
        try:
            if self.model is None:
                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(
                    self.model_name,
                    device='cpu'
                )
                # Log model embedding dimension for verification
                test_emb = self.model.encode("Test", convert_to_numpy=True)
                logger.info(f"Embedding model dimensions: {len(test_emb)}")
            return True
        except Exception as e:
            logger.error(f"Error initializing embeddings model: {str(e)}")
            return False

    def get_embeddings(self, text: str) -> Optional[List[float]]:
        """Generate embeddings for text"""
        try:
            if not self.model and not self.initialize_model():
                return None
            with torch.no_grad():
                embeddings = self.model.encode(
                    text,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                    normalize_embeddings=True
                )
                if isinstance(embeddings, torch.Tensor):
                    return embeddings.cpu().numpy().tolist()
                return list(embeddings)
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return None

    def test_embeddings(self) -> bool:
        """Test if embeddings system is working"""
        try:
            if not self.initialize_model():
                return False
            test_text = "This is a test sentence."
            embeddings = self.get_embeddings(test_text)
            # Verify dimension matches Qdrant configuration
            if embeddings is None:
                return False
            dimension = len(embeddings)
            logger.info(f"Test embedding dimension: {dimension}")
            if dimension != 384:
                logger.error(f"Embedding dimension mismatch: Expected 384, got {dimension}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error testing embeddings: {str(e)}")
            return False

# Export functions that match the original interface
def get_embeddings(text: str) -> Optional[List[float]]:
    return get_manager().get_embeddings(text)

def test_embeddings() -> bool:
    return get_manager().test_embeddings()