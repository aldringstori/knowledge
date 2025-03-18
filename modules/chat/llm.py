import requests
import traceback
from typing import Optional
from utils.logging_setup import logger


def generate_with_model(
        prompt: str,
        model_name: str = "deepseek-r1:8b",  # Accept model name as parameter
        max_tokens: int = 150,
        temperature: float = 0.7,
        timeout: int = 90
) -> str:
    """
    Generate text using the specified model via Ollama API
    """
    try:
        logger.info(f"Generating with model: {model_name}")
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,  # Use the provided model name
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": 512,
                "num_thread": 4
            }
        }

        # Log request summary
        logger.info(f"Request to Ollama: model={model_name}, prompt_length={len(prompt)}, max_tokens={max_tokens}")

        response = requests.post(url, json=payload, timeout=timeout)

        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', 'No response generated')
            logger.info(f"Generation successful: received {len(response_text)} characters")
            return response_text

        # Handle error cases
        error_messages = {
            400: "Bad request. The model input may be invalid.",
            404: f"Model '{model_name}' not found. Please check if it's installed.",
            408: "Request timed out. Try a shorter prompt.",
            500: "Server error. The model might be overloaded.",
            503: "Service unavailable. Please try again in a moment."
        }

        error_msg = error_messages.get(
            response.status_code,
            f"Error {response.status_code} from API"
        )

        logger.error(f"API error: {error_msg}")

        # Try to extract detailed error from response
        try:
            error_details = response.json()
            if 'error' in error_details:
                logger.error(f"API error details: {error_details['error']}")
                error_msg += f" - {error_details['error']}"
        except:
            pass

        return error_msg

    except requests.exceptions.Timeout:
        logger.error(f"Request to model {model_name} timed out after {timeout}s")
        return "The request took too long to process. Please try again."

    except requests.exceptions.ConnectionError:
        logger.error("Connection to Ollama server failed")
        return "Could not connect to the model service. Is it running?"

    except Exception as e:
        logger.error(f"Error generating with model {model_name}: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"


# Backward compatibility alias
def generate_with_phi(prompt, max_tokens=150, temperature=0.7, timeout=90):
    """Legacy function for backward compatibility"""
    logger.warning("generate_with_phi is deprecated, use generate_with_model instead")
    return generate_with_model(prompt, "deepseek-r1:8b", max_tokens, temperature, timeout)