# File: ./modules/chat/rag_manager.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Qdrant
from langchain.memory import ConversationBufferMemory
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from sentence_transformers import CrossEncoder
import os
import glob
from typing import Dict, List, Tuple, Set, Optional  # Added typing imports
from utils.logging_setup import logger


class RAGManager:
    def __init__(self, config: Dict):
        self.config = config
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        self.vector_store = self._initialize_vector_store()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )