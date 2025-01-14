import streamlit as st
import torch
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils.logging_setup import logger
from transformers import GPT2Tokenizer
from models.nanogpt import GPT, GPTConfig
from typing import List, Dict
import glob
import traceback


def setup_qdrant(config):
    """Initialize Qdrant client"""
    try:
        qdrant_path = config['qdrant_path']

        # First try to remove the lock file if it exists
        lock_file = os.path.join(qdrant_path, '.lock')
        if os.path.exists(lock_file):
            os.remove(lock_file)
            logger.info("Removed existing Qdrant lock file")

        # Ensure directory exists with correct permissions
        os.makedirs(qdrant_path, exist_ok=True)
        os.chmod(qdrant_path, 0o755)  # rwxr-xr-x permissions

        # Ensure all files in the directory are writable
        for root, dirs, files in os.walk(qdrant_path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)  # rw-r--r-- permissions

        client = QdrantClient(path=qdrant_path)

        # Create collection if it doesn't exist
        client.recreate_collection(
            collection_name="transcripts",
            vectors_config=models.VectorParams(
                size=768,  # Using GPT2 embedding size
                distance=models.Distance.COSINE
            )
        )
        return client
    except Exception as e:
        logger.error(f"Error setting up Qdrant: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def load_model(config):
    """Load or initialize nanoGPT model"""
    try:
        model_config = GPTConfig(
            block_size=1024,
            vocab_size=50257,  # GPT-2 vocab size
            n_layer=12,
            n_head=12,
            n_embd=768,
            dropout=0.1,
            bias=True
        )
        model = GPT(model_config)

        # Load weights if they exist
        model_path = os.path.join(config['model_path'], 'nanogpt_model.pt')
        if os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path))
            logger.info("Loaded existing model weights")
        else:
            logger.info("No existing model weights found. Using initialized model.")

        model.eval()
        return model
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def setup_tokenizer():
    """Initialize and configure the tokenizer"""
    try:
        tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
        # Ensure tokenizer has padding token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        return tokenizer
    except Exception as e:
        logger.error(f"Error setting up tokenizer: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def ingest_transcripts(client: QdrantClient, config: Dict):
    """Ingest transcripts into Qdrant"""
    try:
        if client is None:
            logger.error("Qdrant client is not initialized")
            return False

        transcript_files = glob.glob(os.path.join(config['download_folder'], '**/*.txt'), recursive=True)
        logger.info(f"Found {len(transcript_files)} transcript files to process")

        tokenizer = setup_tokenizer()
        if tokenizer is None:
            return False

        for file_path in transcript_files:
            try:
                logger.info(f"Processing file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                tokens = tokenizer.encode(text)
                chunk_size = 512
                chunks = [tokens[i:i + chunk_size] for i in range(0, len(tokens), chunk_size)]
                logger.info(f"Split into {len(chunks)} chunks")

                for i, chunk in enumerate(chunks):
                    try:
                        chunk_text = tokenizer.decode(chunk)

                        with torch.no_grad():
                            inputs = tokenizer(
                                chunk_text,
                                return_tensors='pt',
                                padding=True,
                                truncation=True,
                                max_length=512
                            )
                            # Convert to embeddings using PyTorch operations only
                            embeddings = inputs.input_ids.float().mean(dim=1)
                            # Convert to list directly from PyTorch tensor
                            embedding_list = embeddings.tolist()

                        point_id = hash(f"{file_path}_{i}")
                        client.upsert(
                            collection_name="transcripts",
                            points=[
                                models.PointStruct(
                                    id=point_id,
                                    payload={"text": chunk_text, "source": file_path},
                                    vector=embedding_list
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

def generate_response(model, tokenizer, prompt: str, client: QdrantClient) -> str:
    """Generate response using nanoGPT and context from Qdrant"""
    try:
        if None in (model, tokenizer, client):
            logger.error("One or more required components (model, tokenizer, client) not initialized")
            return "I apologize, but the system is not properly initialized."

        # Get relevant context from Qdrant
        with torch.no_grad():
            inputs = tokenizer(
                prompt,
                return_tensors='pt',
                padding=True,
                truncation=True
            )
            prompt_embedding = torch.mean(inputs.input_ids.float(), dim=1)

        search_result = client.search(
            collection_name="transcripts",
            query_vector=prompt_embedding.tolist(),
            limit=5
        )

        # Combine context with prompt
        context = " ".join([hit.payload['text'] for hit in search_result])
        full_prompt = f"{context}\n\nQuestion: {prompt}\nAnswer:"

        # Generate response
        input_ids = tokenizer.encode(full_prompt, return_tensors='pt')
        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=100,
                temperature=0.7,
                top_k=50
            )

        response = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return response.split("Answer:")[-1].strip()

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        logger.error(traceback.format_exc())
        return "I apologize, but I encountered an error while generating the response."

def render(config):
    """Render the chat interface"""
    st.header("Chat with Your Transcripts")

    # Initialize components
    if 'qdrant_client' not in st.session_state:
        st.session_state.qdrant_client = setup_qdrant(config)
    if 'model' not in st.session_state:
        st.session_state.model = load_model(config)
    if 'tokenizer' not in st.session_state:
        st.session_state.tokenizer = setup_tokenizer()

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
            response = generate_response(
                st.session_state.model,
                st.session_state.tokenizer,
                prompt,
                st.session_state.qdrant_client
            )
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})