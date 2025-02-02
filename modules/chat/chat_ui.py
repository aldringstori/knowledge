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

    def render(self):
        """Render the chat interface"""
        st.header("Chat with Your Transcripts")

        # Test embeddings on startup
        if 'embeddings_tested' not in st.session_state:
            with st.spinner("Testing embeddings..."):
                if test_embeddings():
                    st.session_state.embeddings_tested = True
                else:
                    st.error("Error: Embeddings system not working properly")
                    return

        # Settings sidebar
        with st.sidebar:
            st.subheader("Chat Settings")
            st.session_state.max_tokens = st.slider("Max Response Length", 20, 200, 50)
            st.session_state.temperature = st.slider("Temperature", 0.1, 1.0, 0.1)

        # Ingest button
        if st.button("Ingest/Update Transcripts"):
            with st.spinner("Ingesting transcripts..."):
                if self.ingest_documents():
                    st.success("Successfully ingested transcripts!")
                else:
                    st.error("Failed to ingest transcripts. Check logs for details.")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ask about your transcripts"):
            # Display user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate and display assistant response
            with st.chat_message("assistant"):
                response = self.generate_response(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

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