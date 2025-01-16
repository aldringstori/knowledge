import torch
from sentence_transformers import SentenceTransformer
from typing import List, Optional
from utils.logging_setup import logger

MINILM_MODEL = None

def get_minilm_model():
    global MINILM_MODEL
    if MINILM_MODEL is None:
        MINILM_MODEL = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    return MINILM_MODEL


def get_embeddings(text: str) -> Optional[List[float]]:
    try:
        model = get_minilm_model()

        # Normalize input text
        text = text.lower().strip()

        with torch.no_grad():
            # Get embeddings with mean pooling
            embeddings = model.encode(
                text,
                convert_to_tensor=True,
                show_progress_bar=False,
                normalize_embeddings=True  # Important for cosine similarity
            )

            # Convert to list format
            if isinstance(embeddings, torch.Tensor):
                embeddings = embeddings.cpu().numpy().tolist()

            logger.info(f"Generated embeddings of length: {len(embeddings)}")
            return embeddings

    except Exception as e:
        logger.error(f"Error getting embeddings: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def test_embeddings() -> bool:
    try:
        logger.info("Starting embeddings test...")
        model = get_minilm_model()
        logger.info("Model loaded successfully")
        test_text = "This is a test sentence."
        embeddings = get_embeddings(test_text)
        if embeddings is not None:
            logger.info(f"Test embeddings length: {len(embeddings)}")
            return True
        return False
    except Exception as e:
        logger.error(f"Test embeddings failed: {str(e)}")
        return False