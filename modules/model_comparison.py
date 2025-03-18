import streamlit as st
import time
import json
import os
import requests
from datetime import datetime
from queue import Queue
from threading import Thread
import logging

# Set up specific logger for model comparison
model_comparison_logger = logging.getLogger("model_comparison")
model_comparison_logger.setLevel(logging.INFO)

# Create a file handler for the model comparison logs
if not os.path.exists("logs"):
    os.makedirs("logs")
model_log_file = os.path.join("logs", "model_comparison.log")
file_handler = logging.FileHandler(model_log_file)
file_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
model_comparison_logger.addHandler(file_handler)

class ModelComparison:
    def __init__(self):
        self.queue = Queue()
        self.results = {}
        self.worker_running = False
        
    def ollama_request(self, model, prompt):
        """Make a request to Ollama API"""
        try:
            model_comparison_logger.info(f"Sending request to model: {model}")
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120
            )
            if response.status_code == 200:
                result = response.json()
                model_comparison_logger.info(f"Received response from model: {model}")
                return result.get("response", "No response received")
            else:
                error_msg = f"Error with model {model}: {response.status_code} - {response.text}"
                model_comparison_logger.error(error_msg)
                return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Exception with model {model}: {str(e)}"
            model_comparison_logger.error(error_msg)
            return f"Error: {error_msg}"
    
    def worker(self):
        """Process queue items"""
        while not self.queue.empty():
            model, prompt, result_key = self.queue.get()
            self.results[result_key] = {"status": "generating", "response": ""}
            
            response = self.ollama_request(model, prompt)
            
            self.results[result_key] = {
                "status": "completed", 
                "response": response,
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.queue.task_done()
        
        self.worker_running = False
    
    def add_to_queue(self, models, prompt):
        """Add models to the queue for processing"""
        self.results = {}
        
        # Add each model to the queue
        for model in models:
            result_key = f"{model}_{int(time.time())}"
            self.queue.put((model, prompt, result_key))
            self.results[result_key] = {"status": "queued", "response": ""}
            model_comparison_logger.info(f"Added model to queue: {model}")
        
        # Start worker thread if not already running
        if not self.worker_running:
            self.worker_running = True
            worker_thread = Thread(target=self.worker)
            worker_thread.daemon = True
            worker_thread.start()
            model_comparison_logger.info("Started worker thread")
    
    def get_available_models(self):
        """Get list of available models from Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                # Sort models by size (assuming name convention includes size info)
                # You might need to adjust the sorting logic based on your specific model naming
                models = [model["name"] for model in models_data]
                models.sort()  # Simple sort, modify if needed for specific ordering
                return models
            else:
                model_comparison_logger.error(f"Failed to get models: {response.status_code}")
                return []
        except Exception as e:
            model_comparison_logger.error(f"Exception getting models: {str(e)}")
            return []

def render(config):
    st.header("Model Comparison")
    
    # Initialize session state for model comparison
    if 'model_comparison' not in st.session_state:
        st.session_state.model_comparison = ModelComparison()
        
    # Initialize model selection state if not present
    if 'model_selections' not in st.session_state:
        st.session_state.model_selections = {}
    
    # Get available models
    models = st.session_state.model_comparison.get_available_models()
    
    if not models:
        st.error("Unable to fetch models from Ollama. Make sure Ollama is running.")
        if st.button("Retry"):
            st.rerun()
        return
    
    # Section for model selection with checkboxes
    st.subheader("Select Models")
    
    # Use columns to display models in rows for better UI
    cols_per_row = 3
    
    # Initialize default selections (select first 3 models if available)
    for i, model in enumerate(models):
        if model not in st.session_state.model_selections:
            st.session_state.model_selections[model] = i < 3
    
    # Select All / Deselect All buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Select All"):
            for model in models:
                st.session_state.model_selections[model] = True
            st.rerun()
    with col2:
        if st.button("Deselect All"):
            for model in models:
                st.session_state.model_selections[model] = False
            st.rerun()
    
    # Display model checkboxes in rows
    for i in range(0, len(models), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(models):
                model = models[i + j]
                with cols[j]:
                    st.session_state.model_selections[model] = st.checkbox(
                        model, 
                        value=st.session_state.model_selections.get(model, False),
                        key=f"model_checkbox_{model}"
                    )
    
    # Get selected models
    selected_models = [model for model in models if st.session_state.model_selections.get(model, False)]
    
    # Display number of selected models
    st.caption(f"{len(selected_models)} models selected")
    
    # Input prompt
    st.subheader("Enter Prompt")
    prompt = st.text_area("Your prompt for all models", height=150)
    
    # Submit button
    if st.button("Compare Models") and prompt and selected_models:
        model_comparison_logger.info(f"Starting comparison with {len(selected_models)} models")
        st.session_state.model_comparison.add_to_queue(selected_models, prompt)
        st.success(f"Added {len(selected_models)} models to the queue for comparison")
    
    # Display results
    if hasattr(st.session_state, 'model_comparison') and st.session_state.model_comparison.results:
        st.subheader("Results")
        
        # Create columns for each model
        if len(selected_models) > 0:
            cols = st.columns(min(3, len(selected_models)))
            
            # Track result keys by model name for display
            model_to_result_key = {}
            for result_key, result in st.session_state.model_comparison.results.items():
                model_name = result_key.split("_")[0]  # Extract model name from key
                model_to_result_key[model_name] = result_key
            
            # Display results in columns
            for i, model in enumerate(selected_models):
                col_index = i % len(cols)
                with cols[col_index]:
                    result_key = model_to_result_key.get(model)
                    if result_key:
                        result = st.session_state.model_comparison.results[result_key]
                        status = result["status"]
                        
                        # Display model name with status indicator
                        if status == "completed":
                            st.markdown(f"### ✅ {model}")
                        elif status == "generating":
                            st.markdown(f"### ⏳ {model}")
                        else:
                            st.markdown(f"### ⏱️ {model}")
                        
                        # Display response or status
                        if status == "completed":
                            st.text_area(
                                f"Response from {model}",
                                result["response"],
                                height=400,
                                key=f"response_{model}"
                            )
                            st.caption(f"Completed at: {result.get('completed_at', 'Unknown')}")
                        elif status == "generating":
                            st.info("Generating response...")
                            st.spinner()
                        else:
                            st.info("Queued - waiting to process")
                    else:
                        st.markdown(f"### {model}")
                        st.info("Not in current batch")
    
    # Auto-refresh to update status
    if hasattr(st.session_state, 'model_comparison') and any(
            result["status"] in ["queued", "generating"] 
            for result in st.session_state.model_comparison.results.values()):
        time.sleep(1)
        st.rerun()
    
    # View logs section
    with st.expander("View Model Comparison Logs"):
        if os.path.exists(model_log_file):
            with open(model_log_file, "r") as f:
                logs = f.readlines()
            
            # Reverse logs to show newest first
            logs.reverse()
            st.code(''.join(logs), language="text")
            
            if st.button("Clear Model Comparison Logs"):
                with open(model_log_file, "w") as f:
                    f.write("")
                st.success("Logs cleared!")
                st.rerun()
        else:
            st.info("No logs available yet")