from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import os
from utils.logging_setup import logger


class QdrantDB:
    def __init__(self, path: str):
        self.path = path
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[QdrantClient]:
        """Initialize Qdrant client"""
        try:
            os.makedirs(self.path, exist_ok=True)

            # Remove lock file if exists
            lock_file = os.path.join(self.path, '.lock')
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Removed existing Qdrant lock file")

            client = QdrantClient(path=self.path)

            # Initialize collection
            client.recreate_collection(
                collection_name="transcripts",
                vectors_config=models.VectorParams(
                    size=384,  # MiniLM embedding size
                    distance=models.Distance.COSINE
                )
            )

            logger.info("Qdrant client initialized successfully")
            return client

        except Exception as e:
            logger.error(f"Error initializing Qdrant client: {str(e)}")
            return None

    def store_embedding(
            self,
            text: str,
            embedding: List[float],
            source: str,
            point_id: int
    ) -> bool:
        """Store embedding in database"""
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return False

            self.client.upsert(
                collection_name="transcripts",
                points=[
                    models.PointStruct(
                        id=point_id,
                        payload={"text": text, "source": source},
                        vector=embedding
                    )
                ]
            )
            return True

        except Exception as e:
            logger.error(f"Error storing embedding: {str(e)}")
            return False

    def search(
            self,
            vector: List[float],
            limit: int = 3,
            score_threshold: float = 0.7
    ) -> List[Dict]:
        """Search for similar vectors"""
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return []

            results = self.client.search(
                collection_name="transcripts",
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold
            )

            return [
                {
                    'score': hit.score,
                    'payload': hit.payload
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Error searching vectors: {str(e)}")
            return []

    def clear_collection(self):
        """Clear all data from collection"""
        try:
            if self.client:
                self.client.recreate_collection(
                    collection_name="transcripts",
                    vectors_config=models.VectorParams(
                        size=384,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info("Collection cleared successfully")

        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}")