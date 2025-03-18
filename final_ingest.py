#!/usr/bin/env python3
"""
Final ingestion script for Qdrant database with unique considerations:
1. ID is TEXT, not INTEGER
2. UNIQUE constraint on ID
3. The point field is BLOB but currently NULL
"""
import os
import json
import time
import random
import requests
import sqlite3
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# Create logs directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "final_ingest.log")


def log(message):
    """Write message to log file with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} - {message}\n")
    print(f"{timestamp} - {message}")


def load_config():
    """Load settings from settings.json"""
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading settings: {e}")
        return {}


class SpecializedQdrantClient:
    """Specialized Qdrant client for this specific database schema"""

    def __init__(self, path):
        self.path = path
        self.collection_path = os.path.join(path, "collection", "transcripts")
        self.sqlite_path = os.path.join(self.collection_path, "storage.sqlite")
        self.existing_ids = set()

        # Ensure collection directory exists
        if not os.path.exists(self.collection_path):
            os.makedirs(self.collection_path, exist_ok=True)
            log(f"Created collection directory: {self.collection_path}")

        # Get existing IDs to prevent conflicts
        self._load_existing_ids()

    def _load_existing_ids(self):
        """Load existing IDs from the database to avoid conflicts"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Get all existing IDs
            cursor.execute("SELECT id FROM points")
            ids = cursor.fetchall()
            self.existing_ids = set(row[0] for row in ids)

            conn.close()
            log(f"Loaded {len(self.existing_ids)} existing IDs from database")
        except Exception as e:
            log(f"Error loading existing IDs: {e}")

    def _generate_unique_id(self, base_id=None):
        """Generate a unique ID that doesn't conflict with existing ones"""
        if base_id is None:
            # Start with current timestamp + random suffix
            base_id = f"{int(time.time())}{random.randint(1000, 9999)}"

        # If ID already exists, add a suffix
        test_id = base_id
        counter = 1
        while test_id in self.existing_ids:
            test_id = f"{base_id}_{counter}"
            counter += 1

        return test_id

    def store_embedding(self, text, embedding, source, point_id=None):
        """Store embedding in database with proper format for this schema"""
        try:
            # Generate unique ID if not provided
            if point_id is None or str(point_id) in self.existing_ids:
                id_str = self._generate_unique_id()
            else:
                id_str = str(point_id)

            log(f"Using ID: {id_str} for file: {os.path.basename(source)}")

            # Create point data structure
            point_data = {
                "id": id_str,
                "payload": {
                    "text": text,
                    "source": source
                },
                "vector": embedding
            }

            # Serialize to binary
            point_binary = json.dumps(point_data).encode('utf-8')

            # Connect to database
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Insert or replace
            cursor.execute(
                "INSERT OR REPLACE INTO points (id, point) VALUES (?, ?)",
                (id_str, point_binary)
            )

            conn.commit()
            conn.close()

            # Add to existing IDs set
            self.existing_ids.add(id_str)

            log(f"Successfully stored embedding with ID {id_str}")
            return True
        except Exception as e:
            log(f"Error storing embedding: {e}")
            log(traceback.format_exc())
            return False

    def get_ingested_files(self):
        """Get list of ingested files"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Get all points with valid data
            cursor.execute("SELECT point FROM points WHERE point IS NOT NULL")
            rows = cursor.fetchall()

            ingested_files = []
            for row in rows:
                try:
                    # Decode binary point data
                    if row[0] is not None:
                        point_data = json.loads(row[0].decode('utf-8'))
                        source = point_data.get("payload", {}).get("source")
                        if source:
                            ingested_files.append(source)
                except Exception as e:
                    log(f"Error parsing point data: {e}")
                    continue

            conn.close()
            log(f"Found {len(ingested_files)} ingested files with source info")
            return ingested_files
        except Exception as e:
            log(f"Error retrieving ingested files: {e}")
            return []

    def get_collection_stats(self):
        """Get collection statistics"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Count total points
            cursor.execute("SELECT COUNT(*) FROM points")
            total_count = cursor.fetchone()[0]

            # Count points with data
            cursor.execute("SELECT COUNT(*) FROM points WHERE point IS NOT NULL")
            valid_count = cursor.fetchone()[0]

            conn.close()

            return {
                "total_points": total_count,
                "valid_points": valid_count,
                "status": "green" if valid_count > 0 else "yellow"
            }
        except Exception as e:
            log(f"Error getting collection stats: {e}")
            return {"total_points": 0, "valid_points": 0, "status": "red"}

    def cleanup_empty_points(self):
        """Remove points with NULL data"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM points WHERE point IS NULL")
            deleted_count = cursor.rowcount

            conn.commit()
            conn.close()

            log(f"Cleaned up {deleted_count} empty points")
            return deleted_count
        except Exception as e:
            log(f"Error cleaning up empty points: {e}")
            return 0


def ultra_robust_embedding(text: str,
                           max_retries: int = 5,
                           base_timeout: int = 90,
                           backoff_factor: float = 1.5,
                           jitter: float = 0.2) -> Optional[List[float]]:
    """
    Super robust embedding generation designed for very unreliable Ollama servers
    """
    # Maximum text length to prevent overloading Ollama
    MAX_TEXT_LENGTH = 5000
    if len(text) > MAX_TEXT_LENGTH:
        log(f"Text truncated from {len(text)} to {MAX_TEXT_LENGTH} characters")
        text = text[:MAX_TEXT_LENGTH]

    request_id = random.randint(1000, 9999)
    log(f"[{request_id}] Generating embedding for text of length {len(text)}")

    for attempt in range(max_retries):
        # Increase timeout with each retry
        current_timeout = base_timeout * (backoff_factor ** attempt)

        # Add jitter to prevent thundering herd
        jitter_amount = random.uniform(0, jitter * current_timeout)
        adjusted_timeout = current_timeout + jitter_amount

        log(f"[{request_id}] Attempt {attempt + 1}/{max_retries} with timeout {adjusted_timeout:.1f}s")

        try:
            start_time = time.time()
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text:latest", "prompt": text},
                timeout=adjusted_timeout
            )

            response.raise_for_status()
            embedding = response.json().get("embedding")

            if not embedding:
                log(f"[{request_id}] No embedding returned in response")
                time.sleep(backoff_factor ** attempt)
                continue

            if len(embedding) != 768:
                log(f"[{request_id}] Unexpected embedding dimension: {len(embedding)}")
                time.sleep(backoff_factor ** attempt)
                continue

            duration = time.time() - start_time
            log(f"[{request_id}] Successfully generated embedding in {duration:.2f}s")

            return embedding

        except requests.exceptions.Timeout:
            log(f"[{request_id}] Request timed out after {adjusted_timeout:.1f}s")
            if attempt < max_retries - 1:
                sleep_time = (backoff_factor ** attempt) * 5  # Longer sleep after timeout
                log(f"[{request_id}] Waiting {sleep_time:.1f}s before retrying...")
                time.sleep(sleep_time)

        except Exception as e:
            log(f"[{request_id}] Error: {str(e)}")
            if attempt < max_retries - 1:
                sleep_time = backoff_factor ** attempt
                log(f"[{request_id}] Waiting {sleep_time:.1f}s before retrying...")
                time.sleep(sleep_time)

    log(f"[{request_id}] Failed to generate embedding after {max_retries} attempts")
    return None


def process_file(file_path, qdrant_client) -> Tuple[bool, Optional[str]]:
    """Process a single file with robust error handling"""
    file_id = random.randint(1000, 9999)
    log(f"[{file_id}] Processing file: {os.path.basename(file_path)}")

    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        if not text:
            log(f"[{file_id}] Skipping empty file")
            return False, "empty_file"

        log(f"[{file_id}] Read {len(text)} characters")

        # Generate embedding
        embedding = ultra_robust_embedding(text)

        if not embedding:
            log(f"[{file_id}] Failed to generate embedding")
            return False, "embedding_failed"

        # Store in Qdrant (no point_id, will generate unique)
        log(f"[{file_id}] Storing embedding")
        success = qdrant_client.store_embedding(text, embedding, file_path)

        if success:
            log(f"[{file_id}] Successfully stored embedding")
            return True, None
        else:
            log(f"[{file_id}] Failed to store embedding")
            return False, "storage_failed"

    except Exception as e:
        log(f"[{file_id}] Error: {str(e)}")
        log(traceback.format_exc())
        return False, str(e)


def run_final_ingest():
    """Run the final improved ingestion process"""
    # Initialize log
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Final Ingest started at {datetime.now()} ===\n")

    config = load_config()
    if not config:
        log("Failed to load settings.json")
        return

    transcript_path = config.get("transcription_folder", config.get("download_folder"))
    qdrant_path = config.get("qdrant_path")

    if not all([transcript_path, qdrant_path]):
        log("Missing required paths in config")
        return

    log(f"Transcript path: {transcript_path}")
    log(f"Qdrant path: {qdrant_path}")

    # Initialize specialized Qdrant client
    log("Initializing specialized Qdrant client")
    qdrant_client = SpecializedQdrantClient(qdrant_path)

    # Get collection stats
    stats = qdrant_client.get_collection_stats()
    log(f"Collection stats: {stats}")

    # Clean up empty points if needed
    if stats.get("total_points", 0) > 0 and stats.get("valid_points", 0) < stats.get("total_points", 0):
        cleanup = input("Empty points detected. Clean them up? (y/n): ")
        if cleanup.lower() == 'y':
            cleaned = qdrant_client.cleanup_empty_points()
            log(f"Cleaned up {cleaned} empty points")

    # Get already ingested files
    log("Retrieving list of already ingested files")
    ingested_files = qdrant_client.get_ingested_files()
    log(f"Found {len(ingested_files)} already ingested files")

    # Get all available text files
    log(f"Scanning {transcript_path} for .txt files")
    all_files = []
    for root, _, files in os.walk(transcript_path):
        for f in files:
            if f.endswith('.txt'):
                file_path = os.path.join(root, f)
                all_files.append(file_path)

    log(f"Found {len(all_files)} .txt files in total")

    # Determine which files are new
    new_files = [f for f in all_files if f not in ingested_files]
    log(f"Found {len(new_files)} new files to ingest")

    if not new_files:
        log("No new files to ingest. Exiting.")
        return

    # Ask for batch settings
    print("\n=== Final Ingestion Configuration ===")
    print(f"Files to process: {len(new_files)}")

    batch_size = int(input(f"Enter batch size (1-5 recommended): ") or "3")
    max_files = int(input(f"Enter maximum number of files to process (0 for all): ") or "0")
    recovery_time = int(input(f"Enter recovery time between files in seconds (5-15 recommended): ") or "10")
    batch_pause = int(input(f"Enter pause between batches in seconds (20-60 recommended): ") or "30")

    if max_files > 0 and max_files < len(new_files):
        new_files = new_files[:max_files]
        log(f"Limiting to first {max_files} files")

    # Total number of batches
    total_batches = (len(new_files) + batch_size - 1) // batch_size
    log(f"Processing {len(new_files)} files in {total_batches} batches of size {batch_size}")

    # Process in small batches with pauses
    results = {
        "successful": 0,
        "failed": 0,
        "error_types": {}
    }

    # Write checkpoint file to resume if interrupted
    checkpoint_file = os.path.join(LOG_DIR, "ingest_checkpoint.json")

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(new_files))
        batch_files = new_files[batch_start:batch_end]

        log(f"\n=== Processing Batch {batch_idx + 1}/{total_batches} ===")

        for i, file_path in enumerate(batch_files):
            file_idx = batch_start + i + 1
            log(f"File {file_idx}/{len(new_files)}: {os.path.basename(file_path)}")

            # Process file
            success, error_type = process_file(file_path, qdrant_client)

            # Update results
            if success:
                results["successful"] += 1
                ingested_files.append(file_path)
            else:
                results["failed"] += 1
                if error_type:
                    results["error_types"][error_type] = results["error_types"].get(error_type, 0) + 1

            # Write checkpoint
            with open(checkpoint_file, 'w') as f:
                checkpoint = {
                    "processed": file_idx,
                    "total": len(new_files),
                    "successful": results["successful"],
                    "failed": results["failed"],
                    "last_file": file_path,
                    "timestamp": datetime.now().isoformat()
                }
                json.dump(checkpoint, f, indent=2)

            # Progress report
            progress_pct = (file_idx / len(new_files)) * 100
            log(f"Progress: {file_idx}/{len(new_files)} ({progress_pct:.1f}%) - Success: {results['successful']}, Failed: {results['failed']}")

            # Recovery time between files (except for the last file in the batch)
            if i < len(batch_files) - 1:
                log(f"Waiting {recovery_time}s before next file...")
                time.sleep(recovery_time)

        # Pause between batches (except for the last batch)
        if batch_idx < total_batches - 1:
            log(f"Batch {batch_idx + 1} complete. Pausing for {batch_pause}s to let Ollama recover...")
            time.sleep(batch_pause)

    # Final report
    log("\n=== Ingestion Complete ===")
    log(f"Total processed: {len(new_files)}")
    log(f"Successfully ingested: {results['successful']}")
    log(f"Failed: {results['failed']}")

    if results["error_types"]:
        log("\nError distribution:")
        for error_type, count in results["error_types"].items():
            log(f"  {error_type}: {count}")

    # Verify final count
    final_ingested = qdrant_client.get_ingested_files()
    log(f"\nFinal count of files in Qdrant: {len(final_ingested)}")

    print("\n=== Ingestion Summary ===")
    print(f"Files processed: {len(new_files)}")
    print(f"Successfully ingested: {results['successful']} ({results['successful'] / len(new_files) * 100:.1f}%)")
    print(f"Failed: {results['failed']} ({results['failed'] / len(new_files) * 100:.1f}%)")
    print(f"See detailed log at: {LOG_FILE}")


if __name__ == "__main__":
    run_final_ingest()