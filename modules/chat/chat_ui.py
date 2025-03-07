import streamlit as st
from typing import Dict, List, Optional  # Added typing imports
import os
import glob
import time
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
        if 'available_models' not in st.session_state:
            st.session_state.available_models = []
        if 'debug_mode' not in st.session_state:
            st.session_state.debug_mode = False
            
    def ingest_documents(self) -> bool:
        """Ingest documents from transcripts folder with enhanced debugging"""
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
            
            # Get collection stats before ingestion
            before_stats = self.db.get_collection_stats()
            logger.info(f"Collection stats before ingestion: {before_stats}")

            # Track successful and failed files
            success_count = 0
            failed_count = 0
            chunk_count = 0
            
            # Process each file
            for file_path in files:
                try:
                    # Log the file being processed
                    logger.info(f"Processing file: {os.path.basename(file_path)}")
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()

                    # Log text stats
                    logger.info(f"File {os.path.basename(file_path)}: {len(text)} characters, {len(text.split())} words")

                    # Split into chunks
                    words = text.split()
                    chunk_size = 300
                    overlap = 50
                    chunks = []

                    for i in range(0, len(words), chunk_size - overlap):
                        chunk = ' '.join(words[i:i + chunk_size])
                        chunks.append(chunk)

                    logger.info(f"Processing {len(chunks)} chunks for {os.path.basename(file_path)}")

                    # Process each chunk
                    chunk_success = 0
                    chunk_failed = 0
                    
                    for i, chunk_text in enumerate(chunks):
                        try:
                            # Log chunk being processed (first 50 chars)
                            preview = chunk_text[:50] + "..." if len(chunk_text) > 50 else chunk_text
                            logger.info(f"Processing chunk {i+1}/{len(chunks)}: {preview}")
                            
                            # Get embeddings with timing
                            start_time = time.time()
                            embeddings = get_embeddings(chunk_text)
                            embed_time = time.time() - start_time
                            
                            if embeddings:
                                # Log embedding info
                                logger.info(f"Generated embedding: dimension={len(embeddings)}, time={embed_time:.2f}s")
                                
                                # Create a point ID
                                point_id = hash(f"{file_path}_{i}")
                                logger.info(f"Point ID: {point_id}")
                                
                                # Store in database
                                store_result = self.db.store_embedding(
                                    text=chunk_text,
                                    embedding=embeddings,
                                    source=file_path,
                                    point_id=point_id
                                )
                                
                                if store_result:
                                    chunk_success += 1
                                else:
                                    chunk_failed += 1
                                    logger.error(f"Failed to store chunk {i+1} from {os.path.basename(file_path)}")
                            else:
                                chunk_failed += 1
                                logger.error(f"Failed to generate embedding for chunk {i+1} from {os.path.basename(file_path)}")
                                
                        except Exception as e:
                            chunk_failed += 1
                            logger.error(f"Error processing chunk {i+1} from {os.path.basename(file_path)}: {str(e)}")
                    
                    # Log chunk results
                    logger.info(f"File {os.path.basename(file_path)} results: {chunk_success} chunks succeeded, {chunk_failed} chunks failed")
                    
                    chunk_count += chunk_success
                    if chunk_failed == 0:
                        success_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    continue

            # Get collection stats after ingestion
            after_stats = self.db.get_collection_stats()
            logger.info(f"Collection stats after ingestion: {after_stats}")
            
            # Log overall results
            logger.info(f"Document ingestion completed: {success_count} files succeeded, {failed_count} files failed, {chunk_count} chunks stored")
            return True

        except Exception as e:
            logger.error(f"Error during document ingestion: {str(e)}")
            return False

    def generate_response(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate direct response from transcripts with detailed logging"""
        try:
            logger.info(f"Generating response for prompt: {prompt}")
            
            # Get embeddings with timing
            start_time = time.time()
            prompt_embedding = get_embeddings(prompt)
            embedding_time = time.time() - start_time
            
            if not prompt_embedding:
                logger.error("Failed to generate embeddings for prompt")
                return "Error: Could not process your question"

            logger.info(f"Generated prompt embedding: dimension={len(prompt_embedding)}, time={embedding_time:.2f}s")
            
            # Search with timing
            start_time = time.time()
            search_results = self.db.search(
                vector=prompt_embedding,
                limit=5,
                score_threshold=0.7
            )
            search_time = time.time() - start_time
            
            logger.info(f"Search completed in {search_time:.2f}s, found {len(search_results)} results")

            if not search_results:
                logger.warning("No relevant information found in the documents")
                return "No relevant information found in the documents."

            # Process results
            search_results.sort(key=lambda x: x['score'], reverse=True)
            context_texts = []
            sources = set()

            # Log each result
            for i, result in enumerate(search_results[:3]):
                score = result['score']
                source = os.path.basename(result['payload']['source'])
                text_preview = result['payload']['text'][:50] + "..." if len(result['payload']['text']) > 50 else result['payload']['text']
                
                logger.info(f"Result {i+1}: score={score:.4f}, source={source}, text={text_preview}")
                
                context_texts.append(result['payload']['text'])
                if source:
                    sources.add(source)

            # Create prompt
            full_prompt = f"""Based on this transcript content:

{' '.join(context_texts)[:1000]}...

Question: {prompt}

Provide a direct answer using only the information from the transcript content."""

            # Log basic prompt info
            logger.info(f"Created prompt with {len(full_prompt)} characters, {len(sources)} sources")
            
            # Generate model response with timing
            start_time = time.time()
            response = self.model_manager.generate_response(
                prompt=full_prompt,
                max_length=max_tokens,
                temperature=temperature
            )
            generation_time = time.time() - start_time
            
            logger.info(f"Generated response in {generation_time:.2f}s: {len(response)} characters")

            # Add sources if available
            if sources:
                response += f"\n\nSources: {', '.join(sources)}"

            return response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "An error occurred while processing your question."

    def render(self):
        """Render the chat interface with debugging options"""
        st.header("Chat with Your Transcripts")

        # Model Settings Section
        st.subheader("Model Settings")
        
        # Add server connection status indicator
        server_col, status_col = st.columns([3, 1])
        with server_col:
            st.markdown("### Ollama Server")
            check_server = st.button("🔄 Check Server Status")
        
        with status_col:
            if check_server:
                try:
                    response = requests.get("http://localhost:11434/api/version", timeout=3)
                    if response.status_code == 200:
                        version = response.json().get('version', 'unknown')
                        st.success(f"✅ Connected (v{version})")
                    else:
                        st.error("❌ Server Error")
                except Exception as e:
                    st.error("❌ Not Connected")
                    st.info("Make sure Ollama is running on localhost:11434")
        
        st.divider()
        
        model_col1, model_col2 = st.columns([2, 1])
        
        with model_col1:
            # Default model list if none available with preferred smaller model first
            if not st.session_state.available_models:
                st.session_state.available_models = ["deepseek-r1:8b", "deepseek-v2:latest"]
                
            # Add manual model entry option with more robust default
            try:
                update_result = self.update_available_models() if not st.session_state.available_models else True
            except:
                update_result = False
                
            use_manual = st.checkbox("Manually enter model name", value=not update_result)
            
            if use_manual:
                selected_model = st.text_input("Model name:", value=st.session_state.model_name)
                # Button to fetch models from server
                if st.button("🔍 Fetch Models from Server"):
                    if self.update_available_models():
                        st.success("Model list updated!")
                        st.rerun()
                    else:
                        st.error("Failed to fetch models. Is Ollama running?")
            else:
                # Refresh models button
                if st.button("🔄 Refresh Models"):
                    if self.update_available_models():
                        st.success("Model list updated!")
                    else:
                        st.error("Failed to fetch models. Is Ollama running?")
                    
                # Model selection dropdown
                if st.session_state.available_models:
                    selected_model = st.selectbox(
                        "Select Model", 
                        st.session_state.available_models,
                        index=st.session_state.available_models.index(st.session_state.model_name) 
                        if st.session_state.model_name in st.session_state.available_models else 0
                    )
                else:
                    selected_model = st.session_state.model_name
                    st.warning("No models available. Check if Ollama is running.")
            
            # If model changed
            if selected_model != st.session_state.model_name:
                st.session_state.model_name = selected_model
                st.session_state.model_loaded = False
                self.model_manager.set_model(selected_model)
                st.info(f"Model changed to {selected_model}. Please load the model.")
                
        with model_col2:
            # Model status display
            st.markdown("### Model Status")
            if st.session_state.model_loaded:
                st.markdown("**Status:** 🟢 Model Loaded")
            else:
                st.markdown("**Status:** 🔴 Model Not Loaded")
                
            # Show model size info if available
            model_name = st.session_state.model_name
            model_size_info = ""
            
            if hasattr(self.model_manager, 'models_metadata') and model_name in self.model_manager.models_metadata:
                metadata = self.model_manager.models_metadata[model_name]
                if 'size' in metadata:
                    size_gb = metadata['size'] / (1024 * 1024 * 1024)
                    model_size_info = f"Size: {size_gb:.1f} GB"
                    
                if 'details' in metadata and metadata['details']:
                    details = metadata['details']
                    if 'parameter_size' in details:
                        model_size_info += f" | Parameters: {details['parameter_size']}"
                    if 'quantization_level' in details:
                        model_size_info += f" | Quantization: {details['quantization_level']}"
            
            if model_size_info:
                st.markdown(f"**Model Info:**\n{model_size_info}")
            
            # Get model category (small/large)
            model_category = self.model_manager.get_model_category(model_name)
            
            # Load button with clear warning about possible timeouts based on model category
            if model_category == "large":
                load_help = "⚠️ This is a large model that may take 30+ seconds to load and could timeout"
                load_button_text = "Load Large Model"
            else:
                load_help = "This model should load quickly"
                load_button_text = "Load Model"
                
            if st.button(load_button_text, help=load_help):
                progress_text = st.empty()
                progress_text.info(f"Starting to load {st.session_state.model_name}...")
                
                # Set model name
                self.model_manager.set_model(st.session_state.model_name)
                
                # Determine appropriate timeout for progress bar
                timeout = self.model_manager.get_model_timeout(model_name)
                
                # Use progress bar for visual feedback during loading
                with st.spinner(f"Loading {st.session_state.model_name}..."):
                    progress_text.info(f"Initializing {st.session_state.model_name} (this may take up to {timeout} seconds)...")
                    result = self.model_manager.initialize_model()
                    
                    if result:
                        st.session_state.model_loaded = True
                        progress_text.success(f"Model {st.session_state.model_name} loaded successfully!")
                    else:
                        st.session_state.model_loaded = False
                        progress_text.error(f"Error loading model {st.session_state.model_name}")
                        st.error("Failed to load model. Please check logs for details.")
                        st.info("Tips: Try a smaller model like 'deepseek-r1:8b' if you continue to have timeout issues.")

        # Debug mode toggle
        st.sidebar.subheader("Debug Options")
        st.session_state.debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)
        
        # Database diagnostics in debug mode
        if st.session_state.debug_mode:
            st.sidebar.subheader("Database Diagnostics")
            if st.sidebar.button("Get Collection Stats"):
                stats = self.db.get_collection_stats()
                st.sidebar.json(stats)
                
            # Test embeddings button
            if st.sidebar.button("Test Embeddings"):
                with st.sidebar:
                    with st.spinner("Testing embeddings..."):
                        if test_embeddings():
                            st.success("✅ Embeddings test passed")
                            st.info("Embedding dimension: 384")
                        else:
                            st.error("❌ Embeddings test failed")
                            
            # Clear collection button
            if st.sidebar.button("Clear Collection", help="⚠️ This will delete all stored documents"):
                with st.sidebar:
                    with st.spinner("Clearing collection..."):
                        self.db.clear_collection()
                        st.success("Collection cleared")

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
                    # Show stats in debug mode
                    if st.session_state.debug_mode:
                        stats = self.db.get_collection_stats()
                        st.json(stats)
                    st.info("Ready to answer questions about your transcripts.")
                else:
                    st.error("Error ingesting transcripts")

        # Settings sidebar
        with st.sidebar:
            st.subheader("Response Settings")
            max_tokens = st.slider("Max Response Length", 64, 512, 256, 32)
            temperature = st.slider("Temperature", 0.1, 1.0, 0.7, 0.1)

        st.divider()
        st.subheader("Chat")

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
                st.error("Please load the model first using the 'Load Model' button.")
                return

            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Searching transcripts..."):
                    # Show debug info if enabled
                    if st.session_state.debug_mode:
                        start_time = time.time()
                
                    response = self.generate_response(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    # Debug info
                    if st.session_state.debug_mode:
                        total_time = time.time() - start_time
                        st.info(f"Response generated in {total_time:.2f} seconds")
                        
                    st.markdown(response)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response
                    })