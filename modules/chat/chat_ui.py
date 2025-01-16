import streamlit as st
from typing import Dict
from utils.logging_setup import logger
from .embeddings import test_embeddings, get_embeddings
from .llm import generate_with_phi
from .qdrant_db import QdrantDB
from .utils import (
    chunk_text,
    get_transcript_files,
    read_file_content,
    clean_response
)


class ChatUI:
    def __init__(self, config: Dict):
        self.config = config
        self.db = QdrantDB(config['qdrant_path'])

    def ingest_documents(self) -> bool:
        """Ingest documents into the database"""
        try:
            files = get_transcript_files(self.config['download_folder'])
            logger.info(f"Found {len(files)} files to process")

            for file_path in files:
                text = read_file_content(file_path)
                chunks = chunk_text(text)

                for i, chunk in enumerate(chunks):
                    embedding = get_embeddings(chunk)
                    if embedding:
                        self.db.store_embedding(
                            text=chunk,
                            embedding=embedding,
                            source=file_path,
                            point_id=hash(f"{file_path}_{i}")
                        )

            return True
        except Exception as e:
            logger.error(f"Error ingesting documents: {e}")
            return False

    def generate_response(self, prompt: str) -> str:
        try:
            prompt_embedding = get_embeddings(prompt)
            if not prompt_embedding:
                return "Error: Could not generate embeddings for prompt"

            # Search with higher threshold for better matches
            search_results = self.db.search(
                vector=prompt_embedding,
                limit=5,  # Get more results
                score_threshold=0.7  # Only use high-confidence matches
            )

            if not search_results:
                return "No relevant information found in the documents."

            # Sort by score and get best matches
            search_results.sort(key=lambda x: x['score'], reverse=True)

            # Use only the most relevant contexts
            context_texts = [result['text'] for result in search_results[:3]]
            sources = {os.path.basename(result['source'])
                       for result in search_results[:3]}

            full_prompt = f"""Context information: {' '.join(context_texts)[:500]}...

    Question: {prompt}

    Please provide a brief answer using only the information from the context above."""

            response = generate_with_phi(
                full_prompt,
                max_tokens=50,
                temperature=0.1
            )

            cleaned_response = clean_response(response)
            if sources:
                cleaned_response += f"\n\nSources: {', '.join(sources)}"

            return cleaned_response

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "An error occurred while generating the response."