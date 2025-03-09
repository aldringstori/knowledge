# File: ./modules/chat/model_manager.py
import requests
import json
import time
import traceback
from utils.logging_setup import logger


class ModelManager:
    def __init__(self):
        self.model_name = "deepseek-r1:8b"  # Smaller model as default
        self.api_url = "http://localhost:11434/api/generate"
        self.models_list_url = "http://localhost:11434/api/tags"
        self.initialized = False
        self.request_timeout = 120

        # Define model categories by size for better timeout handling
        self.model_sizes = {
            "small": {
                "timeout": 60,
                "max_generation_time": 180,
                "models": ["deepseek-r1:8b", "nezahatkorkmaz/deepseek-v3:latest"]
            },
            "large": {
                "timeout": 120,
                "max_generation_time": 300,
                "models": ["deepseek-v2:latest", "deepseek-coder-v2:16b"]
            }
        }

        # Cache model metadata to avoid repeated API calls
        self.models_metadata = {}

    def get_model_category(self, model_name):
        """Determine if a model is small or large based on known patterns"""
        # First check exact matches in our predefined categories
        for category, info in self.model_sizes.items():
            if model_name in info["models"]:
                return category

        # If not found, check for patterns in the name
        if any(keyword in model_name.lower() for keyword in ["3b", "7b", "8b", "small"]):
            return "small"
        elif any(keyword in model_name.lower() for keyword in ["13b", "14b", "16b", "34b", "70b", "large"]):
            return "large"

        # Default to large if unsure (safer)
        return "large"

    def get_model_timeout(self, model_name):
        """Get appropriate timeout for a model based on its category"""
        category = self.get_model_category(model_name)
        return self.model_sizes[category]["timeout"]

    def get_available_models(self):
        """Get list of available models from Ollama with better error handling"""
        try:
            # Check if server is accessible first with short timeout
            try:
                server_check = requests.get("http://localhost:11434/api/version", timeout=3)
                if server_check.status_code != 200:
                    logger.error(f"Ollama server not responding properly (status {server_check.status_code})")
                    return []
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama server connection failed: {str(e)}")
                return []

            # Now get the models list
            response = requests.get(self.models_list_url, timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                # Extract model names and cache metadata
                if 'models' in models_data:
                    models = []
                    for model in models_data['models']:
                        models.append(model['name'])
                        # Cache model metadata
                        self.models_metadata[model['name']] = {
                            'size': model.get('size', 0),
                            'details': model.get('details', {}),
                            'modified_at': model.get('modified_at', '')
                        }
                    logger.info(f"Found {len(models)} models: {', '.join(models)}")
                    return models
                else:
                    logger.error(f"Unexpected response format from Ollama API: {models_data}")
                    return []
            else:
                logger.error(f"Failed to get models list: {response.status_code}")
                try:
                    err_data = response.json()
                    if 'error' in err_data:
                        logger.error(f"Ollama error: {err_data['error']}")
                except:
                    pass
                return []
        except requests.exceptions.Timeout:
            logger.error("Timeout while getting models list from Ollama server")
            return []
        except Exception as e:
            logger.error(f"Error getting models list: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def set_model(self, model_name):
        """Set the model to use"""
        self.model_name = model_name
        self.initialized = False  # Force reinitialization with new model
        logger.info(f"Model set to {model_name}")

    def initialize_model(self) -> bool:
        """Initialize connection to Ollama with adaptive timeouts based on model size"""
        try:
            logger.info(f"Testing connection to {self.model_name}...")

            # First check if Ollama server is accessible at all
            try:
                # Simply check if the server is up with a short timeout
                server_check = requests.get(
                    "http://localhost:11434/api/version",
                    timeout=5
                )
                if server_check.status_code != 200:
                    logger.error(f"Ollama server not responding properly (status {server_check.status_code})")
                    return False

                logger.info("Ollama server is accessible, attempting to load model...")
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama server connection failed: {str(e)}")
                return False

            # Determine appropriate timeout based on model size
            model_category = self.get_model_category(self.model_name)
            model_timeout = self.model_sizes[model_category]["timeout"]

            logger.info(f"Using {model_timeout}s timeout for {self.model_name} (category: {model_category})")

            # Now try to use the model with appropriate timeout
            payload = {
                "model": self.model_name,
                "prompt": "Hello",  # Simple prompt
                "stream": False,  # Non-streaming for quicker response
                "options": {
                    "num_predict": 10,  # Request minimal output
                    "temperature": 0.1,  # Low temp for deterministic response
                }
            }

            # Make request with progress logging
            start_time = time.time()
            logger.info(f"Sending test request to {self.model_name}...")

            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=model_timeout
                )

                elapsed = time.time() - start_time
                logger.info(f"Model responded in {elapsed:.2f} seconds")

                if response.status_code == 200:
                    self.initialized = True
                    logger.info(f"Successfully connected to {self.model_name}")

                    # If this was exceptionally slow, log a warning
                    if elapsed > 10:
                        logger.warning(f"Model {self.model_name} took {elapsed:.2f}s to respond. " +
                                       "This may indicate slow performance.")

                    return True
                else:
                    logger.error(f"Model initialization failed with status code: {response.status_code}")
                    # Try to extract error message if available
                    try:
                        err_data = response.json()
                        if 'error' in err_data:
                            logger.error(f"Ollama error: {err_data['error']}")
                    except:
                        pass
                    return False

            except requests.exceptions.Timeout:
                logger.error(f"Timeout while connecting to model {self.model_name} after {model_timeout}s.")
                logger.warning(f"This model may be too large or resource-intensive for your hardware.")
                return False

        except requests.exceptions.Timeout:
            logger.error(
                f"Timeout while connecting to model {self.model_name}. Check if the model is available or too large.")
            return False
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def generate_response(
            self,
            prompt: str,
            max_length: int = 512,
            temperature: float = 0.7
    ) -> str:
        """Generate response using streaming with improved error handling"""
        try:
            # Check if model is initialized
            if not self.initialized:
                logger.warning(f"Model {self.model_name} not initialized, attempting to initialize...")
                if not self.initialize_model():
                    return "Model not initialized. Please check if Ollama is running correctly and the model is available."

            # First check if server is responsive
            try:
                server_check = requests.get("http://localhost:11434/api/version", timeout=3)
                if server_check.status_code != 200:
                    logger.error(f"Ollama server not responding properly (status {server_check.status_code})")
                    return "Error: Ollama server is not responding properly. Please check if it's running."
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama server connection failed when generating response: {str(e)}")
                return "Error: Could not connect to Ollama server. Please check if it's running."

            # Get appropriate timeout based on model size
            model_category = self.get_model_category(self.model_name)
            model_timeout = self.model_sizes[model_category]["max_generation_time"]

            # Prepare payload with timeout settings
            payload = {
                "model": self.model_name,  # Use the current model name
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_length,
                    "temperature": temperature,
                    "num_ctx": 4096,
                    "num_thread": 24,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }

            logger.info(f"Generating with model {self.model_name}, timeout={model_timeout}s")

            # Send request with explicit timeout handling
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    stream=True,
                    timeout=model_timeout
                )

                # Check for successful response code
                if response.status_code != 200:
                    try:
                        err_data = response.json()
                        error_msg = err_data.get('error', f"Server returned status code {response.status_code}")
                        logger.error(f"Ollama API error: {error_msg}")
                        return f"Error from Ollama server: {error_msg}"
                    except:
                        logger.error(f"Ollama API returned status code {response.status_code}")
                        return f"Error: Ollama server returned status code {response.status_code}"

                # Collect streaming response with progress info
                full_response = []
                total_chars = 0
                last_log = time.time()

                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                # Skip think/thought tags
                                if '<think>' in chunk['response'] or '</think>' in chunk['response']:
                                    continue
                                full_response.append(chunk['response'])
                                total_chars += len(chunk['response'])

                                # Periodically log progress for long responses
                                now = time.time()
                                if now - last_log > 5:  # Log every 5 seconds
                                    logger.info(f"Received {total_chars} characters of response...")
                                    last_log = now

                            if chunk.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue

                logger.info(f"Response generation complete, received {total_chars} characters")
                return ''.join(full_response).strip()

            except requests.exceptions.Timeout:
                logger.error(f"Timeout error when generating response. Request timeout: {model_timeout}s")
                return "Error: The request to Ollama timed out. The model might be too slow or overloaded."

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            logger.error(traceback.format_exc())
            return f"Error: {str(e)}"
