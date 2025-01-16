import os
from typing import Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils.logging_setup import logger
import traceback


class QdrantDB:
    def __init__(self, path: str):
        self.path = path
        self.client = None

    def setup(self) -> bool:
        try:
            os.makedirs(self.path, exist_ok=True)

            # Remove lock file if exists
            lock_file = os.path.join(self.path, '.lock')
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Removed existing Qdrant lock file")

            # Set permissions
            os.chmod(self.path, 0o777)
            for root, dirs, files in os.walk(self.path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o777)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o666)

            self.client = QdrantClient(path=self.path)
            self.client.recreate_collection(
                collection_name="transcripts",
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )
            return True
        except Exception as e:
            logger.error(f"Error setting up Qdrant: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def check_status(self) -> Dict:
        try:
            collection_info = self.client.get_collection('transcripts')
            points_count = self.client.count('transcripts')
            sample_points = self.client.scroll(
                collection_name='transcripts',
                limit=2
            )[0]

            return {
                'status': 'ok',
                'points_count': points_count,
                'sample_points': sample_points,
                'collection_info': collection_info
            }
        except Exception as e:
            logger.error(f"Error checking Qdrant status: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    def store_embedding(
            self,
            text: str,
            embedding: List[float],
            source: str,
            point_id: Optional[int] = None
    ) -> bool:
        try:
            self.client.upsert(
                collection_name="transcripts",
                points=[
                    models.PointStruct(
                        id=point_id or hash(f"{source}_{text[:50]}"),
                        payload={"text": text, "source": source},
                        vector=embedding
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Error storing embedding: {str(e)}")
            return False

    def search(self, vector: List[float], limit: int = 3, score_threshold: float = 0.7) -> List[Dict]:
        """
        Search for similar documents in Qdrant

        Args:
            vector: Query vector
            limit: Number of results to return
            score_threshold: Minimum similarity score (0 to 1)
        """
        try:
            results = self.client.search(
                collection_name="transcripts",
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold  # Only return results above this similarity
            )

            # Log search results for debugging
            logger.info(f"Search returned {len(results)} results")
            for hit in results:
                logger.info(f"Score: {hit.score}, Text preview: {hit.payload['text'][:100]}...")

            return [
                {
                    'text': hit.payload['text'],
                    'source': hit.payload['source'],
                    'score': hit.score
                }
                for hit in results
                if hit.score > score_threshold  # Double check scores
            ]
        except Exception as e:
            logger.error(f"Error searching: {str(e)}")
            logger.error(traceback.format_exc())
            return []