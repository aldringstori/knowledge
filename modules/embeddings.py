"""
Improved embeddings module with better timeout and retry handling
"""
import requests
import time
import random
from typing import List, Optional

def generate_embedding(text: str,
                     timeout: int = 60,
                     retries: int = 3,
                     backoff_factor: float = 1.5) -> Optional[List[float]]:
    """
    Generate embedding using nomic-embed-text:latest from Ollama server
    with improved timeout and retry logic

    Args:
        text: The text to generate an embedding for
        timeout: Request timeout in seconds (default: 60)
        retries: Number of retry attempts (default: 3)
        backoff_factor: Exponential backoff factor (default: 1.5)

    Returns:
        List of embedding values or None if generation failed
    """
    # Trim text if too long
    MAX_TEXT_LENGTH = 8000
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        print(f"Text truncated to {MAX_TEXT_LENGTH} characters")

    # Try up to 'retries' times
    for attempt in range(retries):
        try:
            # Use longer timeout and add request identifier for logging
            request_id = random.randint(1000, 9999)
            print(f"[{request_id}] Requesting embedding for text of length {len(text)} (attempt {attempt+1}/{retries})")

            start_time = time.time()
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text:latest", "prompt": text},
                timeout=timeout  # Increased timeout
            )

            response.raise_for_status()
            embedding = response.json().get("embedding")

            if not embedding:
                print(f"[{request_id}] No embedding returned in response")
                if attempt < retries - 1:
                    time.sleep(backoff_factor ** attempt)  # Exponential backoff
                continue

            if len(embedding) != 768:
                print(f"[{request_id}] Unexpected embedding dimension: {len(embedding)}")
                if attempt < retries - 1:
                    time.sleep(backoff_factor ** attempt)
                continue

            duration = time.time() - start_time
            print(f"[{request_id}] Successfully generated embedding in {duration:.2f}s")

            return embedding

        except requests.exceptions.Timeout:
            print(f"[{request_id}] Request timed out after {timeout}s")
            if attempt < retries - 1:
                sleep_time = backoff_factor ** attempt
                print(f"[{request_id}] Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)

        except Exception as e:
            print(f"[{request_id}] Error: {str(e)}")
            if attempt < retries - 1:
                sleep_time = backoff_factor ** attempt
                print(f"[{request_id}] Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)

    # If we get here, all retries failed
    print(f"Failed to generate embedding after {retries} attempts")
    return None