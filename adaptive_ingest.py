#!/usr/bin/env python3
"""
Adaptive ingestion script that inspects and adapts to the existing Qdrant schema
"""
import os
import json
import time
import random
import requests
import sqlite3
import traceback
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# Create logs directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "adaptive_ingest.log")


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


class AdaptiveQdrantClient:
    """Adaptive Qdrant client that inspects and adapts to the existing database schema"""

    def __init__(self, path):
        self.path = path
        self.collection_path = os.path.join(path, "collection", "transcripts")
        self.sqlite_path = os.path.join(self.collection_path, "storage.sqlite")
        self.schema = {}

        # Ensure collection directory exists
        if not os.path.exists(self.collection_path):
            os.makedirs(self.collection_path, exist_ok=True)
            log(f"Created collection directory: {self.collection_path}")

        # Inspect schema or initialize database
        if os.path.exists(self.sqlite_path):
            self._inspect_schema()
        else:
            self._init_db()

    def _inspect_schema(self):
        """Inspect the existing database schema"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            self.schema['tables'] = [table[0] for table in tables]
            log(f"Found tables: {self.schema['tables']}")

            # Get columns for relevant tables
            self.schema['columns'] = {}
            self.schema['data_structure'] = 'unknown'

            if 'points' in self.schema['tables']:
                cursor.execute("PRAGMA table_info(points);")
                columns = cursor.fetchall()
                self.schema['columns']['points'] = [col[1] for col in columns]
                log(f"Points table columns: {self.schema['columns']['points']}")

                # Check if we have a sample row to determine storage format
                cursor.execute("SELECT * FROM points LIMIT 1;")
                sample = cursor.fetchone()

                if sample:
                    log(f"Sample row structure (first 100 chars): {str(sample)[:100]}...")

                    # Try to determine the schema type based on columns
                    if 'payload' in self.schema['columns']['points'] and 'vector' in self.schema['columns']['points']:
                        self.schema['data_structure'] = 'json_payload_vector'
                        log("Schema format: JSON payload and vector")
                    elif 'payload' not in self.schema['columns']['points'] and len(
                            self.schema['columns']['points']) > 2:
                        self.schema['data_structure'] = 'direct_columns'
                        log("Schema format: Direct columns (no payload field)")
                    else:
                        self.schema['data_structure'] = 'unknown'
                        log("Schema format: Unknown")

            conn.close()
            log("Successfully inspected database schema")
        except Exception as e:
            log(f"Error inspecting schema: {e}")
            log(traceback.format_exc())

    def _init_db(self):
        """Initialize a new SQLite database"""
        try:
            log(f"Creating new SQLite database at {self.sqlite_path}")
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Create points table with flexible schema
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS points
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY,
                               source
                               TEXT,
                               text
                               TEXT,
                               vector
                               TEXT
                           )
                           ''')

            conn.commit()
            conn.close()

            # Update schema info
            self.schema = {
                'tables': ['points'],
                'columns': {'points': ['id', 'source', 'text', 'vector']},
                'data_structure': 'direct_columns'
            }

            log("Successfully initialized new database")
        except Exception as e:
            log(f"Error initializing database: {e}")
            log(traceback.format_exc())

    def store_embedding(self, text, embedding, source, point_id):
        """Store embedding in database, adapting to the existing schema"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Handle based on schema type
            if self.schema.get('data_structure') == 'json_payload_vector':
                # Format with payload and vector as JSON
                payload = json.dumps({"text": text, "source": source})
                vector_json = json.dumps(embedding)

                # Check if ID already exists
                cursor.execute("SELECT id FROM points WHERE id = ?", (point_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing point
                    cursor.execute(
                        "UPDATE points SET payload = ?, vector = ? WHERE id = ?",
                        (payload, vector_json, point_id)
                    )
                else:
                    # Insert new point
                    cursor.execute(
                        "INSERT INTO points (id, payload, vector) VALUES (?, ?, ?)",
                        (point_id, payload, vector_json)
                    )

            elif self.schema.get('data_structure') == 'direct_columns':
                # Format with direct columns
                vector_json = json.dumps(embedding)

                # Check if ID already exists
                cursor.execute("SELECT id FROM points WHERE id = ?", (point_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing point
                    cursor.execute(
                        "UPDATE points SET source = ?, text = ?, vector = ? WHERE id = ?",
                        (source, text, vector_json, point_id)
                    )
                else:
                    # Insert new point
                    cursor.execute(
                        "INSERT INTO points (id, source, text, vector) VALUES (?, ?, ?, ?)",
                        (point_id, source, text, vector_json)
                    )

            else:
                # Unknown schema, try to create a basic structure
                log(f"Using unknown schema structure, attempting basic insert")

                # Create table if not exists
                if 'points' not in self.schema.get('tables', []):
                    cursor.execute('''
                                   CREATE TABLE IF NOT EXISTS points
                                   (
                                       id
                                       INTEGER
                                       PRIMARY
                                       KEY,
                                       source
                                       TEXT,
                                       text
                                       TEXT,
                                       vector
                                       TEXT
                                   )
                                   ''')

                vector_json = json.dumps(embedding)

                # Check columns and make a best-effort insert
                cursor.execute("PRAGMA table_info(points);")
                columns = [col[1] for col in cursor.fetchall()]

                if 'id' in columns:
                    # Insert with available columns
                    fields = ['id']
                    values = [point_id]

                    if 'source' in columns:
                        fields.append('source')
                        values.append(source)

                    if 'text' in columns:
                        fields.append('text')
                        values.append(text)

                    if 'vector' in columns:
                        fields.append('vector')
                        values.append(vector_json)

                    # Construct dynamic query
                    query = f"INSERT INTO points ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(values))})"
                    cursor.execute(query, values)

            conn.commit()
            conn.close()

            log(f"Successfully stored embedding with ID {point_id}")
            return True
        except Exception as e:
            log(f"Error storing embedding: {e}")
            log(traceback.format_exc())
            return False

    def get_ingested_files(self):
        """Get list of already ingested files, adapting to the schema"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            ingested_files = []

            # Handle based on schema type
            if self.schema.get('data_structure') == 'json_payload_vector':
                # Extract source from JSON payload
                cursor.execute("SELECT payload FROM points")
                rows = cursor.fetchall()

                for row in rows:
                    try:
                        payload = json.loads(row[0])
                        source = payload.get("source")
                        if source:
                            ingested_files.append(source)
                    except:
                        continue

            elif self.schema.get('data_structure') == 'direct_columns':
                # Get source directly from column
                cursor.execute("SELECT source FROM points")
                rows = cursor.fetchall()

                for row in rows:
                    if row[0]:
                        ingested_files.append(row[0])

            else:
                # Unknown schema, try to find source data
                # Check if 'source' column exists
                cursor.execute("PRAGMA table_info(points);")
                columns = [col[1] for col in cursor.fetchall()]

                if 'source' in columns:
                    cursor.execute("SELECT source FROM points")
                    rows = cursor.fetchall()

                    for row in rows:
                        if row[0]:
                            ingested_files.append(row[0])
                elif 'payload' in columns:
                    cursor.execute("SELECT payload FROM points")
                    rows = cursor.fetchall()

                    for row in rows:
                        try:
                            payload = json.loads(row[0])
                            source = payload.get("source")
                            if source:
                                ingested_files.append(source)
                        except:
                            continue

            conn.close()
            log(f"Retrieved {len(ingested_files)} ingested files")
            return ingested_files
        except Exception as e:
            log(f"Error retrieving ingested files: {e}")
            log(traceback.format_exc())
            return []

    def get_collection_stats(self):
        """Get collection statistics"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()

            # Make sure points table exists
            if 'points' not in self.schema.get('tables', []):
                conn.close()
                return {"points_count": 0, "status": "yellow"}

            cursor.execute("SELECT COUNT(*) FROM points")
            count = cursor.fetchone()[0]

            conn.close()

            return {
                "points_count": count,
                "status": "green" if count >= 0 else "yellow"
            }
        except Exception as e:
            log(f"Error getting collection stats: {e}")
            return {"points_count": 0, "status": "red"}


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


def process_file(file_path, qdrant_client, point_id) -> Tuple[bool, Optional[str]]:
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

        # Store in Qdrant
        log(f"[{file_id}] Storing embedding with ID {point_id}")
        success = qdrant_client.store_embedding(text, embedding, file_path, point_id)

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


def run_adaptive_ingest():
    """Run adaptive ingestion process"""
    # Initialize log
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Adaptive Ingest started at {datetime.now()} ===\n")

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

    # Initialize adaptive Qdrant client
    log("Initializing adaptive Qdrant client")
    qdrant_client = AdaptiveQdrantClient(qdrant_path)

    # Get collection stats
    stats = qdrant_client.get_collection_stats()
    log(f"Collection stats: {stats}")

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
    print("\n=== Adaptive Ingestion Configuration ===")
    print(f"Files to process: {len(new_files)}")

    batch_size = int(input(f"Enter batch size (1-5 recommended): ") or "3")
    max_files = int(input(f"Enter maximum number of files to process (0 for all): ") or "0")
    recovery_time = int(input(f"Enter recovery time between files in seconds (10-30 recommended): ") or "15")
    batch_pause = int(input(f"Enter pause between batches in seconds (30-120 recommended): ") or "60")

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
            point_id = len(ingested_files) + results["successful"] + 1
            success, error_type = process_file(file_path, qdrant_client, point_id)

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
    run_adaptive_ingest()