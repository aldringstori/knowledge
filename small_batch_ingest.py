#!/usr/bin/env python3
"""
Small batch ingestion script with improved timeout handling

This script processes files in small batches with improved embedding generation
to handle Ollama timeout issues.
"""
import os
import json
import time
from datetime import datetime
from modules.embeddings import generate_embedding
from modules.chat.qdrant_db import QdrantDB

# Create logs directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "small_batch_ingest.log")


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


def process_batch(files, qdrant_db, ingested_files, batch_number, total_batches):
    """Process a batch of files"""
    batch_size = len(files)
    log(f"Processing batch {batch_number}/{total_batches} ({batch_size} files)")

    successful = 0
    failed = 0

    for i, file in enumerate(files):
        file_index = i + 1
        log(f"[Batch {batch_number}] Processing file {file_index}/{batch_size}: {os.path.basename(file)}")

        try:
            # Read file
            with open(file, 'r', encoding='utf-8') as f:
                text = f.read().strip()

            if not text:
                log(f"[Batch {batch_number}] Skipping empty file: {os.path.basename(file)}")
                continue

            # Generate embedding with improved function
            embedding = generate_embedding(text, timeout=60, retries=3)

            if not embedding:
                log(f"[Batch {batch_number}] Failed to generate embedding for {os.path.basename(file)}")
                failed += 1
                continue

            # Store embedding
            point_id = len(ingested_files) + successful + 1
            success = qdrant_db.store_embedding(text, embedding, file, point_id)

            if success:
                successful += 1
                ingested_files.append(file)
                log(f"[Batch {batch_number}] Successfully ingested {os.path.basename(file)}")
            else:
                failed += 1
                log(f"[Batch {batch_number}] Failed to store embedding for {os.path.basename(file)}")

        except Exception as e:
            failed += 1
            log(f"[Batch {batch_number}] Error processing {os.path.basename(file)}: {e}")

    # Batch summary
    log(f"Batch {batch_number} complete: {successful} successful, {failed} failed")
    return successful, failed


def run_small_batch_ingest():
    """Run ingestion in small batches with pauses between batches"""
    # Initialize log
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Small Batch Ingestion Log started at {datetime.now()} ===\n")

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

    # Initialize Qdrant
    log("Initializing Qdrant database")
    qdrant_db = QdrantDB(qdrant_path)

    # Get already ingested files
    log("Retrieving list of already ingested files")
    ingested_files = qdrant_db.get_ingested_files()
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
    batch_size = int(input(f"Enter batch size (recommended: 5-10): ") or "5")
    max_batches = int(input(f"Enter maximum number of batches to process (or 0 for all): ") or "0")
    pause_between = int(input(f"Enter pause between batches in seconds (recommended: 10-30): ") or "15")

    # Determine batches
    total_batches = (len(new_files) + batch_size - 1) // batch_size
    if max_batches > 0 and max_batches < total_batches:
        log(f"Limiting to {max_batches} batches (out of {total_batches} total)")
        total_batches = max_batches
    else:
        log(f"Processing all {total_batches} batches")

    # Process in batches
    total_successful = 0
    total_failed = 0

    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(new_files))
        batch_files = new_files[start_idx:end_idx]

        # Process batch
        batch_start_time = time.time()
        successful, failed = process_batch(batch_files, qdrant_db, ingested_files, batch_num, total_batches)
        batch_end_time = time.time()

        # Update totals
        total_successful += successful
        total_failed += failed

        # Batch stats
        batch_duration = batch_end_time - batch_start_time
        log(f"Batch {batch_num} took {batch_duration:.2f} seconds")

        # Progress report
        log(f"Progress: {total_successful}/{len(new_files)} files ingested successfully ({total_failed} failed)")

        # Pause between batches (except after the last batch)
        if batch_num < total_batches:
            log(f"Pausing for {pause_between} seconds before next batch...")
            time.sleep(pause_between)

    # Final report
    log("=== Ingestion Complete ===")
    log(f"Total files ingested successfully: {total_successful}")
    log(f"Total files failed: {total_failed}")
    log(f"Total files skipped: {len(new_files) - (total_successful + total_failed)}")

    # Verify final count
    final_ingested = qdrant_db.get_ingested_files()
    log(f"Final count of files in Qdrant: {len(final_ingested)}")


if __name__ == "__main__":
    run_small_batch_ingest()