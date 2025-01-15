import streamlit as st
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils.logging_setup import logger
from typing import List, Dict, Optional
import glob
import traceback
from sentence_transformers import SentenceTransformer
import requests
import torch
from torch import Tensor

# Initialize models globally
MINILM_MODEL = None


def get_minilm_model():
    global MINILM_MODEL
    if MINILM_MODEL is None:
        MINILM_MODEL = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    return MINILM_MODEL


def test_embeddings():
    """Test function to verify embeddings are working"""
    try:
        logger.info("Starting embeddings test...")

        # Test model loading
        model = get_minilm_model()
        logger.info("Model loaded successfully")

        # Test basic encoding
        test_text = "This is a test sentence."
        logger.info(f"Testing encoding of: {test_text}")

        embeddings = get_embeddings(test_text)
        if embeddings is not None:
            logger.info(f"Test embeddings length: {len(embeddings)}")
            return True

        logger.error("Embeddings are None")
        return False

    except Exception as e:
        logger.error(f"Test embeddings failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False


def setup_qdrant(config):
    """Initialize Qdrant client"""
    try:
        qdrant_path = config['qdrant_path']
        os.makedirs(qdrant_path, exist_ok=True)

        # Remove lock file if it exists
        lock_file = os.path.join(qdrant_path, '.lock')
        if os.path.exists(lock_file):
            os.remove(lock_file)
            logger.info("Removed existing Qdrant lock file")

        # Set permissions
        os.chmod(qdrant_path, 0o777)
        for root, dirs, files in os.walk(qdrant_path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o777)
            for f in files:
                os.chmod(os.path.join(root, f), 0o666)

        client = QdrantClient(path=qdrant_path)
        # Using MiniLM embedding size (384)
        client.recreate_collection(
            collection_name="transcripts",
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE
            )
        )
        return client
    except Exception as e:
        logger.error(f"Error setting up Qdrant: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def get_embeddings(text: str) -> List[float]:
    """Get embeddings using MiniLM model"""
    try:
        model = get_minilm_model()
        logger.info("Model loaded successfully")

        # Generate embeddings
        with torch.no_grad():
            embeddings = model.encode(
                text,
                convert_to_tensor=True,
                show_progress_bar=False
            )
            logger.info(f"Generated embeddings type: {type(embeddings)}")

            # Convert tensor to list directly without numpy
            if isinstance(embeddings, torch.Tensor):
                embeddings = embeddings.tolist()
                logger.info("Converted tensor to list successfully")
                return embeddings

            # If already a list or numpy array
            if hasattr(embeddings, 'tolist'):
                return embeddings.tolist()

            return list(embeddings)

    except Exception as e:
        logger.error(f"Error getting embeddings: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def generate_with_phi(prompt: str, max_tokens: int = 150, temperature: float = 0.7) -> str:
    """Generate response using Phi model"""
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "phi3:3.8b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": 512,
                "num_thread": 4
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=90)  # Increased timeout

            if response.status_code == 200:
                result = response.json()
                if 'response' in result:
                    return result['response']
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return "Error: Unexpected response format from model."

            # Handle specific error codes
            error_messages = {
                408: "Request timed out. Try a shorter prompt.",
                500: "Server error. The model might be overloaded.",
                503: "Service unavailable. Please try again in a moment."
            }
            error_msg = error_messages.get(response.status_code, f"Error {response.status_code} from API")
            logger.error(f"{error_msg}: {response.text}")
            return error_msg

        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            return "The request took too long to process. Please try again."
        except requests.exceptions.ConnectionError:
            logger.error("Connection failed")
            return "Could not connect to the model service. Is it running?"

    except Exception as e:
        logger.error(f"Error generating with Phi: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"

def ingest_transcripts(client: QdrantClient, config: Dict) -> bool:
    """Ingest transcripts into Qdrant"""
    try:
        if client is None:
            logger.error("Qdrant client is not initialized")
            return False

        transcript_files = glob.glob(os.path.join(config['download_folder'], '**/*.txt'), recursive=True)
        logger.info(f"Found {len(transcript_files)} transcript files to process")

        for file_path in transcript_files:
            try:
                logger.info(f"Processing file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                # Split text into chunks (300 words with 50 word overlap)
                words = text.split()
                chunk_size = 300
                overlap = 50
                chunks = []

                for i in range(0, len(words), chunk_size - overlap):
                    chunk = ' '.join(words[i:i + chunk_size])
                    chunks.append(chunk)

                logger.info(f"Split into {len(chunks)} chunks")

                for i, chunk_text in enumerate(chunks):
                    try:
                        embeddings = get_embeddings(chunk_text)
                        if embeddings is None:
                            continue

                        point_id = hash(f"{file_path}_{i}")
                        client.upsert(
                            collection_name="transcripts",
                            points=[
                                models.PointStruct(
                                    id=point_id,
                                    payload={"text": chunk_text, "source": file_path},
                                    vector=embeddings
                                )
                            ]
                        )
                        if i % 10 == 0:
                            logger.info(f"Processed {i}/{len(chunks)} chunks for {os.path.basename(file_path)}")

                    except Exception as chunk_error:
                        logger.error(f"Error processing chunk {i} of {file_path}: {str(chunk_error)}")
                        logger.error(traceback.format_exc())
                        continue

            except Exception as file_error:
                logger.error(f"Error processing file {file_path}: {str(file_error)}")
                logger.error(traceback.format_exc())
                continue

        logger.info("Completed transcript ingestion")
        return True

    except Exception as e:
        logger.error(f"Error in ingest_transcripts: {str(e)}")
        logger.error(traceback.format_exc())
        return False


def generate_response(prompt: str, client: QdrantClient) -> str:
    """Generate response using context from Qdrant and Phi model"""
    try:
        # Get relevant context from Qdrant
        prompt_embedding = get_embeddings(prompt)
        if prompt_embedding is None:
            return "Error: Could not generate embeddings"

        search_result = client.search(
            collection_name="transcripts",
            query_vector=prompt_embedding,
            limit=3  # Reduced for more focused context
        )

        # Extract and format context
        context_texts = [hit.payload['text'] for hit in search_result]
        sources = [os.path.basename(hit.payload['source']) for hit in search_result]
        formatted_context = " ".join(context_texts)

        # Create prompt with source attribution
        full_prompt = f"""Context: {formatted_context[:500]}...

Question: {prompt}

Please provide a brief answer based on the context. Sources: {', '.join(sources)}

Answer: """

        # Generate response with Phi
        response = generate_with_phi(
            full_prompt,
            max_tokens=50,  # Shorter responses
            temperature=0.1  # More focused
        )

        # Clean up response
        if "Context:" in response:
            response = response.split("Context:")[-1]
        if "Answer:" in response:
            response = response.split("Answer:")[-1]
        if "Sources:" in response:
            response = response.split("Sources:")[0]

        # Add source attribution
        response = response.strip() + f"\n\nSources: {', '.join(sources)}"

        return response

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        logger.error(traceback.format_exc())
        return "I apologize, but I encountered an error while generating the response."


def render(config):
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
        st.subheader("Settings")
        st.session_state.max_tokens = st.slider("Max Response Length", 20, 200, 50)
        st.session_state.temperature = st.slider("Temperature", 0.1, 1.0, 0.1)

    # Initialize Qdrant client
    if 'qdrant_client' not in st.session_state:
        st.session_state.qdrant_client = setup_qdrant(config)

    # Ingest button
    if st.button("Ingest/Update Transcripts"):
        with st.spinner("Ingesting transcripts..."):
            success = ingest_transcripts(st.session_state.qdrant_client, config)
            if success:
                st.success("Successfully ingested transcripts!")
            else:
                st.error("Failed to ingest transcripts. Check logs for details.")

    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
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
            response = generate_response(prompt, st.session_state.qdrant_client)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})