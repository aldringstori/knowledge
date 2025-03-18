#!/usr/bin/env python3
"""
Direct debugging script for Qdrant ingestion issues
This script contains all necessary code to test the ingestion process directly
without relying on existing module imports.
"""
import os
import sys
import json
import requests
import sqlite3
import time
from datetime import datetime

# Create logs directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


# Set up direct file logging
def log_to_file(log_file, message):
    """Write message directly to log file with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} - {message}\n")


# Log files
QDRANT_LOG = os.path.join(LOG_DIR, "qdrant_direct.log")
DATA_LOG = os.path.join(LOG_DIR, "data_direct.log")

# Initialize log files with headers
for log_file in [QDRANT_LOG, DATA_LOG]:
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"=== Log started at {datetime.now()} ===\n")


def load_config():
    """Load settings from settings.json"""
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
        log_to_file(DATA_LOG, f"Error loading settings: {e}")
        return {}


def test_ollama_connection():
    """Test connection to Ollama server"""
    print("Testing Ollama connection...")
    log_to_file(DATA_LOG, "Testing Ollama connection...")

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        available_models = [model.get("name") for model in models]

        message = f"Connected to Ollama server. Available models: {available_models}"
        print(message)
        log_to_file(DATA_LOG, message)

        if "nomic-embed-text:latest" in available_models:
            print("✅ nomic-embed-text:latest is available")
            log_to_file(DATA_LOG, "nomic-embed-text:latest is available")
        else:
            print("❌ nomic-embed-text:latest is NOT available")
            log_to_file(DATA_LOG, "nomic-embed-text:latest is NOT available")

        return True
    except requests.RequestException as e:
        error_msg = f"Failed to connect to Ollama server: {e}"
        print(f"❌ {error_msg}")
        log_to_file(DATA_LOG, error_msg)
        print("Make sure Ollama is running (ollama serve)")
        return False


def test_embedding(text="Test embedding"):
    """Test generating an embedding"""
    print("Testing embedding generation...")
    log_to_file(DATA_LOG, f"Testing embedding generation for text: '{text[:50]}...'")

    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text:latest", "prompt": text},
            timeout=10
        )
        response.raise_for_status()
        embedding = response.json().get("embedding")

        if embedding and len(embedding) == 768:
            message = f"Embedding generated successfully: {len(embedding)} dimensions"
            print(f"✅ {message}")
            log_to_file(DATA_LOG, message)
            return embedding
        else:
            error_msg = f"Invalid embedding: {'None' if not embedding else f'Dimension {len(embedding)}'}"
            print(f"❌ {error_msg}")
            log_to_file(DATA_LOG, error_msg)
            return None
    except Exception as e:
        error_msg = f"Failed to generate embedding: {e}"
        print(f"❌ {error_msg}")
        log_to_file(DATA_LOG, error_msg)
        return None


def inspect_qdrant_db(qdrant_path):
    """Directly inspect Qdrant database files"""
    print(f"Inspecting Qdrant DB at {qdrant_path}...")
    log_to_file(QDRANT_LOG, f"Inspecting Qdrant DB at {qdrant_path}")

    if not os.path.exists(qdrant_path):
        print(f"❌ Qdrant path doesn't exist: {qdrant_path}")
        log_to_file(QDRANT_LOG, f"Qdrant path doesn't exist: {qdrant_path}")
        return

    # Look for collection directory
    collection_path = os.path.join(qdrant_path, "collection")
    if not os.path.exists(collection_path):
        print(f"❌ Collection directory missing: {collection_path}")
        log_to_file(QDRANT_LOG, f"Collection directory missing: {collection_path}")
        return

    # Look for transcripts collection
    transcripts_path = os.path.join(collection_path, "transcripts")
    if not os.path.exists(transcripts_path):
        print(f"❌ Transcripts collection missing: {transcripts_path}")
        log_to_file(QDRANT_LOG, f"Transcripts collection missing: {transcripts_path}")
        return

    # Check SQLite file
    sqlite_path = os.path.join(transcripts_path, "storage.sqlite")
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite file missing: {sqlite_path}")
        log_to_file(QDRANT_LOG, f"SQLite file missing: {sqlite_path}")
        return

    print(f"✅ Found SQLite file: {sqlite_path}")
    log_to_file(QDRANT_LOG, f"Found SQLite file: {sqlite_path}")

    # Try to read SQLite database directly
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in database: {tables}")
        log_to_file(QDRANT_LOG, f"Tables in database: {tables}")

        # Check for points table
        if ('points',) in tables:
            cursor.execute("SELECT COUNT(*) FROM points;")
            point_count = cursor.fetchone()[0]
            print(f"Number of points in database: {point_count}")
            log_to_file(QDRANT_LOG, f"Number of points in database: {point_count}")

            # Get sample points
            if point_count > 0:
                cursor.execute("SELECT id, payload FROM points LIMIT 3;")
                sample_points = cursor.fetchall()
                print(f"Sample points: {sample_points}")
                log_to_file(QDRANT_LOG, f"Sample points: {sample_points}")

        conn.close()
        return True
    except Exception as e:
        error_msg = f"Error reading SQLite database: {e}"
        print(f"❌ {error_msg}")
        log_to_file(QDRANT_LOG, error_msg)
        return False


def check_file_permissions(path):
    """Check read/write permissions on a path"""
    print(f"Checking permissions for {path}...")
    log_to_file(DATA_LOG, f"Checking permissions for {path}")

    if not os.path.exists(path):
        print(f"❌ Path doesn't exist: {path}")
        log_to_file(DATA_LOG, f"Path doesn't exist: {path}")
        return False

    # Check if directory
    is_dir = os.path.isdir(path)
    print(f"Is directory: {is_dir}")

    # Check read permission
    can_read = os.access(path, os.R_OK)
    print(f"Can read: {can_read}")
    log_to_file(DATA_LOG, f"Can read: {can_read}")

    # Check write permission
    can_write = os.access(path, os.W_OK)
    print(f"Can write: {can_write}")
    log_to_file(DATA_LOG, f"Can write: {can_write}")

    # Check execute permission (for directories)
    can_execute = os.access(path, os.X_OK)
    print(f"Can execute: {can_execute}")
    log_to_file(DATA_LOG, f"Can execute: {can_execute}")

    # Get stat information
    try:
        stat_info = os.stat(path)
        perms = oct(stat_info.st_mode)[-3:]
        owner = stat_info.st_uid
        group = stat_info.st_gid
        print(f"Owner: {owner}, Group: {group}, Permissions: {perms}")
        log_to_file(DATA_LOG, f"Owner: {owner}, Group: {group}, Permissions: {perms}")
    except Exception as e:
        error_msg = f"Error getting stat info: {e}"
        print(f"❌ {error_msg}")
        log_to_file(DATA_LOG, error_msg)

    # Try to write a test file if it's a directory
    if is_dir:
        test_file = os.path.join(path, ".test_write_permission")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            print("✅ Successfully wrote test file")
            log_to_file(DATA_LOG, "Successfully wrote test file")
            os.remove(test_file)
            print("✅ Successfully deleted test file")
            log_to_file(DATA_LOG, "Successfully deleted test file")
        except Exception as e:
            error_msg = f"Error writing test file: {e}"
            print(f"❌ {error_msg}")
            log_to_file(DATA_LOG, error_msg)

    return can_read and can_write


def test_ingest_sample(transcript_path, qdrant_path):
    """Test the full ingestion process with a sample file"""
    print("\nTesting full ingestion process with a sample file...")
    log_to_file(DATA_LOG, "Testing full ingestion process with a sample file")

    # Find a sample text file
    sample_file = None
    for root, _, files in os.walk(transcript_path):
        for f in files:
            if f.endswith('.txt'):
                sample_file = os.path.join(root, f)
                break
        if sample_file:
            break

    if not sample_file:
        print("❌ No .txt files found in transcription folder")
        log_to_file(DATA_LOG, "No .txt files found in transcription folder")
        return False

    print(f"Using sample file: {sample_file}")
    log_to_file(DATA_LOG, f"Using sample file: {sample_file}")

    # Read sample file
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        file_size = len(text)
        print(f"Read {file_size} characters from file")
        log_to_file(DATA_LOG, f"Read {file_size} characters from file")

        if file_size == 0:
            print("❌ Sample file is empty")
            log_to_file(DATA_LOG, "Sample file is empty")
            return False

        # Truncate if too large
        if file_size > 10000:
            text = text[:10000]
            print(f"Truncated text to 10000 characters for testing")
            log_to_file(DATA_LOG, "Truncated text to 10000 characters for testing")
    except Exception as e:
        error_msg = f"Error reading sample file: {e}"
        print(f"❌ {error_msg}")
        log_to_file(DATA_LOG, error_msg)
        return False

    # Generate embedding
    print("Generating embedding...")
    log_to_file(DATA_LOG, "Generating embedding")
    embedding = test_embedding(text)

    if embedding is None:
        print("❌ Failed to generate embedding")
        log_to_file(DATA_LOG, "Failed to generate embedding")
        return False

    # Simple manual storage in Qdrant
    try:
        # Initialize Qdrant client
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        print("Initializing Qdrant client...")
        log_to_file(QDRANT_LOG, "Initializing Qdrant client")

        client = QdrantClient(path=qdrant_path)

        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        print(f"Existing collections: {collection_names}")
        log_to_file(QDRANT_LOG, f"Existing collections: {collection_names}")

        if "transcripts" not in collection_names:
            print("Creating 'transcripts' collection...")
            log_to_file(QDRANT_LOG, "Creating 'transcripts' collection")
            client.recreate_collection(
                collection_name="transcripts",
                vectors_config=models.VectorParams(
                    size=768,  # Nomic embedding size
                    distance=models.Distance.COSINE
                )
            )

        # Store embedding
        print("Storing embedding...")
        log_to_file(QDRANT_LOG, "Storing embedding")

        client.upsert(
            collection_name="transcripts",
            points=[
                models.PointStruct(
                    id=1,
                    payload={"text": text, "source": sample_file},
                    vector=embedding
                )
            ]
        )

        print("✅ Successfully stored embedding")
        log_to_file(QDRANT_LOG, "Successfully stored embedding")

        # Verify it was stored
        result = client.retrieve(
            collection_name="transcripts",
            ids=[1]
        )

        if result:
            print("✅ Successfully retrieved point")
            log_to_file(QDRANT_LOG, "Successfully retrieved point")
            return True
        else:
            print("❌ Failed to retrieve point")
            log_to_file(QDRANT_LOG, "Failed to retrieve point")
            return False
    except Exception as e:
        error_msg = f"Error during Qdrant operations: {e}"
        print(f"❌ {error_msg}")
        log_to_file(QDRANT_LOG, error_msg)
        return False


def run_diagnostics():
    """Run comprehensive diagnostics"""
    print("=== Direct Qdrant Ingestion Diagnostics ===")
    log_to_file(DATA_LOG, "Starting direct diagnostics")

    config = load_config()
    if not config:
        print("Failed to load settings.json")
        return

    transcript_path = config.get("transcription_folder", config.get("download_folder"))
    qdrant_path = config.get("qdrant_path")

    print(f"Transcript path: {transcript_path}")
    print(f"Qdrant path: {qdrant_path}")

    if not all([transcript_path, qdrant_path]):
        print("Missing required paths in config")
        return

    # Test 1: Ollama connection
    print("\n1. Testing Ollama connection")
    ollama_working = test_ollama_connection()

    # Test 2: Embedding generation
    print("\n2. Testing embedding generation")
    embedding_working = test_embedding() is not None

    # Test 3: File permissions
    print("\n3. Checking file permissions")
    transcript_permissions = check_file_permissions(transcript_path)
    qdrant_permissions = check_file_permissions(qdrant_path)

    # Test 4: Qdrant DB inspection
    print("\n4. Inspecting Qdrant database")
    qdrant_db_ok = inspect_qdrant_db(qdrant_path)

    # Test 5: Full ingestion test
    print("\n5. Testing full ingestion process")
    if ollama_working and transcript_permissions and qdrant_permissions:
        ingest_ok = test_ingest_sample(transcript_path, qdrant_path)
    else:
        print("Skipping ingestion test due to previous failures")
        ingest_ok = False

    # Report summary
    print("\n=== Diagnostic Summary ===")
    print(f"Ollama connection: {'✅' if ollama_working else '❌'}")
    print(f"Embedding generation: {'✅' if embedding_working else '❌'}")
    print(f"Transcript folder permissions: {'✅' if transcript_permissions else '❌'}")
    print(f"Qdrant folder permissions: {'✅' if qdrant_permissions else '❌'}")
    print(f"Qdrant database access: {'✅' if qdrant_db_ok else '❌'}")
    print(f"Sample ingestion test: {'✅' if ingest_ok else '❌'}")

    # Log summary
    log_to_file(DATA_LOG, "=== Diagnostic Summary ===")
    log_to_file(DATA_LOG, f"Ollama connection: {ollama_working}")
    log_to_file(DATA_LOG, f"Embedding generation: {embedding_working}")
    log_to_file(DATA_LOG, f"Transcript folder permissions: {transcript_permissions}")
    log_to_file(DATA_LOG, f"Qdrant folder permissions: {qdrant_permissions}")
    log_to_file(DATA_LOG, f"Qdrant database access: {qdrant_db_ok}")
    log_to_file(DATA_LOG, f"Sample ingestion test: {ingest_ok}")

    print("\nDetailed logs written to:")
    print(f"- {DATA_LOG}")
    print(f"- {QDRANT_LOG}")


if __name__ == "__main__":
    run_diagnostics()