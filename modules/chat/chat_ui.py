# File: ./modules/chat/chat_ui.py
import streamlit as st
from typing import Dict, List, Optional  # Added typing imports
import os
import glob
from utils.logging_setup import logger
from .embeddings import test_embeddings, get_embeddings
from .model_manager import ModelManager
from .qdrant_db import QdrantDB

class ChatUI:
    def __init__(self, config: Dict):
        self.config = config
        self.model_manager = ModelManager()
        self.db = QdrantDB(config['qdrant_path'])
        # Add model status to session state
        if 'model_loaded' not in st.session_state:
            st.session_state.model_loaded = False
        if 'model_name' not in st.session_state:
            st.session_state.model_name = "deepseek-r1:8b"

    def ingest_documents(self) -> bool:
        """Ingest documents from transcripts folder"""
        try:
            transcript_path = "/srv/knowledge/transcriptions"
            if not os.path.exists(transcript_path):
                logger.error(f"Transcriptions directory not found: {transcript_path}")
                return False

            # Find all text files
            files = glob.glob(os.path.join(transcript_path, "**/*.txt"), recursive=True)
            if not files:
                logger.warning("No transcript files found")
                return False

            logger.info(f"Found {len(files)} transcript files to process")

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()

                    # Split into chunks
                    words = text.split()
                    chunk_size = 300
                    overlap = 50
                    chunks = []

                    for i in range(0, len(words), chunk_size - overlap):
                        chunk = ' '.join(words[i:i + chunk_size])
                        chunks.append(chunk)

                    logger.info(f"Processing {len(chunks)} chunks for {os.path.basename(file_path)}")

                    for i, chunk_text in enumerate(chunks):
                        embeddings = get_embeddings(chunk_text)
                        if embeddings:
                            point_id = hash(f"{file_path}_{i}")
                            self.db.store_embedding(
                                text=chunk_text,
                                embedding=embeddings,
                                source=file_path,
                                point_id=point_id
                            )

                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    continue

            logger.info("Document ingestion completed")
            return True

        except Exception as e:
            logger.error(f"Error during document ingestion: {str(e)}")
            return False

    def generate_response(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate direct response from transcripts"""
        try:
            prompt_embedding = get_embeddings(prompt)
            if not prompt_embedding:
                return "Error: Could not process your question"

            search_results = self.db.search(
                vector=prompt_embedding,
                limit=5,
                score_threshold=0.7
            )

            if not search_results:
                return "No relevant information found in the documents."

            search_results.sort(key=lambda x: x['score'], reverse=True)
            context_texts = []
            sources = set()

            for result in search_results[:3]:
                context_texts.append(result['payload']['text'])
                source = os.path.basename(result['payload']['source'])
                if source:
                    sources.add(source)

            full_prompt = f"""Based on this transcript content:

{' '.join(context_texts)[:1000]}...

Question: {prompt}

Provide a direct answer using only the information from the transcript content."""

            response = self.model_manager.generate_response(
                prompt=full_prompt,
                max_length=max_tokens,
                temperature=temperature
            )

            if sources:
                response += f"\n\nSources: {', '.join(sources)}"

            return response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "An error occurred while processing your question."

    def render(self):
        """Render the chat interface"""
        st.header("Chat with Your Transcripts")

        # Model Status Display
        model_status_col1, model_status_col2 = st.columns([2, 1])
        with model_status_col1:
            st.markdown(f"**Current Model:** {st.session_state.model_name}")
        with model_status_col2:
            if st.session_state.model_loaded:
                st.markdown("**Status:** 🟢 Model Loaded")
            else:
                st.markdown("**Status:** 🔴 Model Not Loaded")

        # Test embeddings on startup
        if 'embeddings_tested' not in st.session_state:
            with st.spinner("Testing embeddings..."):
                if test_embeddings():
                    st.session_state.embeddings_tested = True
                else:
                    st.error("Error: Embeddings system not working properly")
                    return

        # Add Ingest button to main interface
        if st.button("Ingest Transcripts"):
            with st.spinner("Processing transcripts..."):
                if self.ingest_documents():
                    st.success("Transcripts ingested successfully!")
                    st.info("Ready to answer questions about your transcripts.")
                else:
                    st.error("Error ingesting transcripts")

        # Settings sidebar
        with st.sidebar:
            st.subheader("Settings")
            max_tokens = st.slider("Max Response Length", 64, 512, 256, 32)
            temperature = st.slider("Temperature", 0.1, 1.0, 0.7, 0.1)

            if st.button("Load/Reload Model"):
                with st.spinner("Loading model..."):
                    if self.model_manager.initialize_model():
                        st.session_state.model_loaded = True
                        st.success(f"Model {st.session_state.model_name} loaded successfully!")
                    else:
                        st.session_state.model_loaded = False
                        st.error(f"Error loading model {st.session_state.model_name}")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ask about your transcripts"):
            if not st.session_state.model_loaded:
                st.error("Please load the model first using the 'Load/Reload Model' button in settings.")
                return

            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Searching transcripts..."):
                    response = self.generate_response(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    st.markdown(response)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response
                    })