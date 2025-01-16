import os
from typing import List, Dict
import glob
from utils.logging_setup import logger


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks


def get_transcript_files(directory: str) -> List[str]:
    """Get all .txt files recursively from directory"""
    return glob.glob(os.path.join(directory, '**/*.txt'), recursive=True)


def read_file_content(file_path: str) -> str:
    """Read content from file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""


def clean_response(response: str) -> str:
    """Clean up model response"""
    response = response.strip()

    # Remove potential prefixes
    for prefix in ["Context:", "Question:", "Answer:", "Sources:"]:
        if prefix in response:
            response = response.split(prefix)[-1]

    return response.strip()