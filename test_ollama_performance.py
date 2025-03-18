#!/usr/bin/env python3
"""
Ollama performance testing script
Tests Ollama's embedding generation performance and reliability
"""
import requests
import time
import statistics
import argparse
import random
import os
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_system_resources():
    """Get current system resource usage"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_gb": memory.available / (1024 ** 3),
        "disk_percent": disk.percent,
        "disk_free_gb": disk.free / (1024 ** 3)
    }


def test_single_embedding(text_length=1000, timeout=30):
    """Test generating a single embedding with random text"""
    # Generate random text of specified length
    text = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz ') for _ in range(text_length))

    start_time = time.time()
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text:latest", "prompt": text},
            timeout=timeout
        )
        response.raise_for_status()
        embedding = response.json().get("embedding")

        end_time = time.time()
        duration = end_time - start_time

        return {
            "success": True,
            "duration": duration,
            "dim": len(embedding) if embedding else None,
            "text_length": text_length
        }
    except Exception as e:
        end_time = time.time()
        return {
            "success": False,
            "error": str(e),
            "duration": end_time - start_time,
            "text_length": text_length
        }


def run_sequential_test(count=10, text_length=1000, timeout=30):
    """Run sequential embedding tests"""
    print(f"Running {count} sequential embedding tests with text length {text_length}...")

    results = []
    for i in range(count):
        print(f"Test {i + 1}/{count}...")
        result = test_single_embedding(text_length, timeout)
        results.append(result)

        if result["success"]:
            print(f"  Success: {result['duration']:.2f}s")
        else:
            print(f"  Failed: {result['error']}")

    return results


def run_concurrent_test(count=10, concurrency=4, text_length=1000, timeout=30):
    """Run concurrent embedding tests"""
    print(f"Running {count} concurrent embedding tests (max {concurrency} at once) with text length {text_length}...")

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(test_single_embedding, text_length, timeout) for _ in range(count)]

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            results.append(result)

            if result["success"]:
                print(f"Test {i + 1}/{count} completed: {result['duration']:.2f}s")
            else:
                print(f"Test {i + 1}/{count} failed: {result['error']}")

    return results


def analyze_results(results):
    """Analyze test results"""
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    success_rate = len(successful) / len(results) if results else 0

    print("\n=== Results Analysis ===")
    print(f"Total tests: {len(results)}")
    print(f"Successful: {len(successful)} ({success_rate * 100:.1f}%)")
    print(f"Failed: {len(failed)}")

    if successful:
        durations = [r["duration"] for r in successful]
        print(f"\nDuration statistics (seconds):")
        print(f"  Min: {min(durations):.2f}")
        print(f"  Max: {max(durations):.2f}")
        print(f"  Mean: {statistics.mean(durations):.2f}")
        print(f"  Median: {statistics.median(durations):.2f}")
        if len(durations) > 1:
            print(f"  Std Dev: {statistics.stdev(durations):.2f}")

    if failed:
        print("\nError distribution:")
        error_counts = {}
        for r in failed:
            error_type = r["error"].split(':')[0]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count} occurrences")


def main():
    parser = argparse.ArgumentParser(description="Test Ollama embedding performance")
    parser.add_argument("--count", type=int, default=10, help="Number of embedding tests to run")
    parser.add_argument("--length", type=int, default=1000, help="Length of random text to use")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds")
    parser.add_argument("--concurrent", action="store_true", help="Run tests concurrently")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers")
    args = parser.parse_args()

    # Check if Ollama is available
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        available_models = [model.get("name") for model in models]

        if "nomic-embed-text:latest" not in available_models:
            print("Warning: nomic-embed-text:latest model is not available in Ollama")
            print(f"Available models: {available_models}")
            return
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        print("Make sure Ollama is running (ollama serve)")
        return

    # Get system resources before tests
    print("=== System Resources Before Test ===")
    resources_before = get_system_resources()
    for key, value in resources_before.items():
        if 'percent' in key:
            print(f"{key}: {value}%")
        elif 'gb' in key:
            print(f"{key}: {value:.2f} GB")
        else:
            print(f"{key}: {value}")

    # Run tests
    start_time = time.time()
    if args.concurrent:
        results = run_concurrent_test(args.count, args.workers, args.length, args.timeout)
    else:
        results = run_sequential_test(args.count, args.length, args.timeout)
    end_time = time.time()

    # Get system resources after tests
    print("\n=== System Resources After Test ===")
    resources_after = get_system_resources()
    for key, value in resources_after.items():
        if 'percent' in key:
            print(f"{key}: {value}%")
        elif 'gb' in key:
            print(f"{key}: {value:.2f} GB")
        else:
            print(f"{key}: {value}")

    # Analyze results
    analyze_results(results)

    # Print overall statistics
    total_duration = end_time - start_time
    print(f"\nTotal test duration: {total_duration:.2f} seconds")
    print(f"Average time per request: {total_duration / args.count:.2f} seconds")


if __name__ == "__main__":
    main()