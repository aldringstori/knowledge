from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import os
import json
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
            
            # Check if collection exists
            collections = client.get_collections()
            logger.info(f"Existing collections: {[c.name for c in collections.collections]}")
            
            # Initialize collection
            client.recreate_collection(
                collection_name="transcripts",
                vectors_config=models.VectorParams(
                    size=384,  # MiniLM embedding size
                    distance=models.Distance.COSINE
                )
            )
            
            # Verify collection was created properly
            collection_info = client.get_collection(collection_name="transcripts")
            logger.info(f"Collection info: Vector size={collection_info.config.params.size}, " +
                        f"Distance={collection_info.config.params.distance}")
            
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
                
            # Log embedding dimension for debugging
            emb_dimension = len(embedding)
            logger.info(f"Storing embedding: id={point_id}, dimension={emb_dimension}, source={os.path.basename(source)}")
            
            # Verify embedding dimension matches collection
            collection_info = self.client.get_collection(collection_name="transcripts")
            expected_dimension = collection_info.config.params.size
            
            if emb_dimension != expected_dimension:
                logger.error(f"Dimension mismatch: embedding={emb_dimension}, collection={expected_dimension}")
                return False
                
            # Store first few values of embedding for debugging
            logger.info(f"Sample values: {embedding[:5]}...")
                
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
            
            # Verify point was stored
            count = self.client.count(collection_name="transcripts")
            logger.info(f"Total points in collection after insert: {count.count}")
            
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
                
            # Log search vector dimension
            query_dimension = len(vector)
            logger.info(f"Searching with vector dimension: {query_dimension}")
            
            # Get collection dimension
            collection_info = self.client.get_collection(collection_name="transcripts")
            expected_dimension = collection_info.config.params.size
            
            # Check dimensions match
            if query_dimension != expected_dimension:
                logger.error(f"Search vector dimension mismatch: query={query_dimension}, collection={expected_dimension}")
                return []
                
            # Check if collection is empty
            count = self.client.count(collection_name="transcripts")
            if count.count == 0:
                logger.warning("Search attempted on empty collection")
                return []
                
            # Log search parameters
            logger.info(f"Searching with limit={limit}, threshold={score_threshold}")
            logger.info(f"Sample query vector values: {vector[:5]}...")
                
            results = self.client.search(
                collection_name="transcripts",
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Log results summary
            logger.info(f"Search returned {len(results)} results")
            for i, hit in enumerate(results):
                logger.info(f"Result {i+1}: score={hit.score:.4f}, " +
                           f"source={os.path.basename(hit.payload.get('source', 'unknown'))}")
                           
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
                # Log before clearing
                count_before = self.client.count(collection_name="transcripts")
                logger.info(f"Clearing collection with {count_before.count} points")
                
                self.client.recreate_collection(
                    collection_name="transcripts",
                    vectors_config=models.VectorParams(
                        size=384,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Verify collection is empty
                count_after = self.client.count(collection_name="transcripts")
                logger.info(f"Collection cleared successfully. Points after clear: {count_after.count}")
        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}")
            
    def get_collection_stats(self) -> Dict:
        """Get statistics about the collection"""
        try:
            if not self.client:
                logger.error("Qdrant client not initialized")
                return {"error": "Client not initialized"}
                
            # Get collection info
            collection_info = self.client.get_collection(collection_name="transcripts")
            vector_size = collection_info.config.params.size
            
            # Count points
            count = self.client.count(collection_name="transcripts")
            
            # Get a sample point if collection is not empty
            sample_point = None
            if count.count > 0:
                sample_points = self.client.scroll(
                    collection_name="transcripts",
                    limit=1
                )
                if sample_points[0]:
                    sample_point = {
                        "id": sample_points[0][0].id,
                        "payload_keys": list(sample_points[0][0].payload.keys()),
                        "vector_dimension": len(sample_points[0][0].vector)
                    }
            
            stats = {
                "count": count.count,
                "vector_size": vector_size,
                "sample_point": sample_point
            }
            
            logger.info(f"Collection stats: {json.dumps(stats, indent=2)}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}