from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain_core.retrievers import BaseRetriever
from sentence_transformers import CrossEncoder
import numpy as np
from typing import Dict, List, Tuple, Optional
from utils.logging_setup import logger

class RAGManager:
    def __init__(self, config: Dict):
        """Initialize the RAG manager with configuration"""
        try:
            self.config = config
            # Use the same model as in embeddings.py - MiniLM with 384 dimensions
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,
            )
            self.vector_store = self._initialize_vector_store()
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
            logger.info("RAG manager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing RAG manager: {str(e)}")
            raise