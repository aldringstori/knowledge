from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import os
import random
import time
from utils.logging_setup import get_qdrant_logger

# Get the Qdrant-specific logger
logger = get_qdrant_logger()


class QdrantDB:
    def __init__(self, path: str):
        self.path = path
        logger.info(f"Initializing QdrantDB with path: {path}")
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[QdrantClient]:
        """Initialize Qdrant client"""
        try:
            os.makedirs(self.path, exist_ok=True)
            lock_file = os.path.join(self.path, '.lock')
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"Removed existing Qdrant lock file: {lock_file}")

            logger.debug(f"Creating Qdrant client with path: {self.path}")
            client = QdrantClient(path=self.path)

            collections = client.get_collections().collections
            collection_names = [c.name for c in collections]
            logger.debug(f"Existing collections: {collection_names}")

            if "transcripts" not in collection_names:
                logger.info("Creating new 'transcripts' collection with 768 dimensions")
                client.recreate_collection(
                    collection_name="transcripts",
                    vectors_config=models.VectorParams(
                        size=768,  # Nomic embedding size
                        distance=models.Distance.COSINE
                    )
                )
                logger.info("Created new 'transcripts' collection successfully")
            else:
                logger.info("'transcripts' collection already exists")

            logger.info("Qdrant client initialized successfully")
            return client
        except Exception as e:
            logger.error(f"Error initializing Qdrant client: {str(e)}", exc_info=True)
            return None

    def store_embedding(
            self,
            text: str,
            embedding: List[float],
            source: str,
            point_id=None
    ) -> bool:
        """
        Store embedding in database

        Args:
            text: The text content
            embedding: The embedding vector
            source: Source file path
            point_id: Optional ID (if not provided, a unique ID will be generated)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return False

            # Generate a unique ID if not provided
            if point_id is None:
                point_id = f"{int(time.time())}{random.randint(1000, 9999)}"
                logger.debug(f"Generated unique ID: {point_id}")

            # Ensure point_id is a string
            point_id = str(point_id)

            emb_dimension = len(embedding)
            logger.debug(
                f"Storing embedding: id={point_id}, dimension={emb_dimension}, source={os.path.basename(source)}")

            collection_info = self.client.get_collection(collection_name="transcripts")
            expected_dimension = collection_info.config.params.vectors.size

            if emb_dimension != expected_dimension:
                logger.error(f"Dimension mismatch: embedding={emb_dimension}, collection={expected_dimension}")
                return False

            # Check if embedding contains NaN or null values
            if not all(isinstance(x, (int, float)) for x in embedding) or any(
                    x != x for x in embedding):  # x != x checks for NaN
                logger.error(f"Invalid values in embedding for point_id={point_id}")
                return False

            logger.debug(f"Upserting point_id={point_id} to transcripts collection")
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

            logger.info(f"Successfully stored embedding for {os.path.basename(source)} with ID {point_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing embedding for {os.path.basename(source)}: {str(e)}", exc_info=True)
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

            logger.debug(f"Searching with threshold={score_threshold}, limit={limit}")
            results = self.client.search(
                collection_name="transcripts",
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold
            )

            logger.info(f"Search completed, found {len(results)} results")
            for i, hit in enumerate(results):
                logger.debug(f"Result {i + 1}: score={hit.score}, source={hit.payload.get('source')}")
            return [{'score': hit.score, 'payload': hit.payload} for hit in results]
        except Exception as e:
            logger.error(f"Error searching vectors: {str(e)}", exc_info=True)
            return []

    def clear_collection(self):
        """Clear all data from collection"""
        try:
            if self.client:
                logger.info("Clearing 'transcripts' collection")
                self.client.recreate_collection(
                    collection_name="transcripts",
                    vectors_config=models.VectorParams(
                        size=768,  # Nomic embedding size
                        distance=models.Distance.COSINE
                    )
                )
                logger.info("Collection cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}", exc_info=True)

    def get_ingested_files(self) -> List[str]:
        """Retrieve list of ingested files from Qdrant"""
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return []

            logger.debug("Retrieving list of ingested files")
            ingested_files = set()
            next_offset = None

            while True:
                logger.debug(f"Scrolling with offset={next_offset}")
                scroll_result = self.client.scroll(
                    collection_name="transcripts",
                    scroll_filter=None,
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                    offset=next_offset
                )

                points, next_offset = scroll_result

                for point in points:
                    source = point.payload.get('source')
                    if source:
                        ingested_files.add(source)

                if not next_offset:
                    break

            logger.info(f"Retrieved {len(ingested_files)} ingested files")
            return list(ingested_files)
        except Exception as e:
            logger.error(f"Error retrieving ingested files: {str(e)}", exc_info=True)
            return []

    def get_collection_stats(self) -> Dict:
        """Get statistics about the transcripts collection"""
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return {"points_count": 0}

            logger.debug("Retrieving collection stats")
            info = self.client.get_collection(collection_name="transcripts")
            stats = {
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status
            }
            logger.info(f"Collection stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error retrieving collection stats: {str(e)}", exc_info=True)
            return {"points_count": 0}