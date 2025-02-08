# File: ./modules/chat/model_manager.py
import requests
import json
from utils.logging_setup import logger
import traceback


class ModelManager:
    def __init__(self):
        self.model_name = "deepseek-r1:8b"
        self.api_url = "http://localhost:11434/api/generate"
        self.initialized = False
        self.request_timeout = 120

    def initialize_model(self) -> bool:
        """Initialize connection to Ollama"""
        try:
            logger.info(f"Testing connection to {self.model_name}...")

            payload = {
                "model": self.model_name,
                "prompt": "test",
                "stream": True
            }

            response = requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=30
            )

            # Check first response chunk
            for line in response.iter_lines():
                if line:
                    self.initialized = True
                    logger.info(f"Successfully connected to {self.model_name}")
                    return True
                break

            return False

        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            return False

    def generate_response(
            self,
            prompt: str,
            max_length: int = 512,
            temperature: float = 0.7
    ) -> str:
        """Generate response using streaming"""
        try:
            if not self.initialized and not self.initialize_model():
                return "Model not initialized. Please check if Ollama is running correctly."

            payload = {
                "model": self.model_name,
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

            response = requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=self.request_timeout
            )

            # Collect streaming response
            full_response = []
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            # Skip think/thought tags
                            if '<think>' in chunk['response'] or '</think>' in chunk['response']:
                                continue
                            full_response.append(chunk['response'])
                        if chunk.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue

            return ''.join(full_response).strip()

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            logger.error(traceback.format_exc())
            return f"Error: {str(e)}"