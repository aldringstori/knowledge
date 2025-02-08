import requests
import traceback
from typing import Optional
from utils.logging_setup import logger


def generate_with_phi(
        prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        timeout: int = 90
) -> str:
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "deepseek-r1:8b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": 512,
                "num_thread": 4
            }
        }

        response = requests.post(url, json=payload, timeout=timeout)

        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'No response generated')

        error_messages = {
            408: "Request timed out. Try a shorter prompt.",
            500: "Server error. The model might be overloaded.",
            503: "Service unavailable. Please try again in a moment."
        }
        return error_messages.get(response.status_code, f"Error {response.status_code} from API")

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