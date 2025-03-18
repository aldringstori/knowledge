#!/usr/bin/env python3
"""
Inspect the existing Qdrant SQLite schema
"""
import os
import json
import sqlite3
import sys


def inspect_sqlite_file(sqlite_path):
    """Inspect the structure of a SQLite database file"""
    print(f"Inspecting SQLite file: {sqlite_path}")

    if not os.path.exists(sqlite_path):
        print(f"File not found: {sqlite_path}")
        return

    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in database: {tables}")

        # Inspect each table
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print("Columns:")
            for col in columns:
                print(f"  {col}")

            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"Row count: {count}")

            # Get sample data if available
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
                sample = cursor.fetchone()
                print(f"Sample row: {sample}")

        conn.close()
    except Exception as e:
        print(f"Error inspecting database: {e}")


def main():
    # Get Qdrant path from settings.json or command line
    qdrant_path = None

    # Try to load from settings.json
    try:
        with open('settings.json', 'r') as f:
            config = json.load(f)
            qdrant_path = config.get("qdrant_path")
    except Exception as e:
        print(f"Error loading settings.json: {e}")

    # Allow override from command line
    if len(sys.argv) > 1:
        qdrant_path = sys.argv[1]

    if not qdrant_path:
        qdrant_path = input("Enter Qdrant path: ")

    if not os.path.exists(qdrant_path):
        print(f"Path does not exist: {qdrant_path}")
        return

    # Find SQLite file
    sqlite_path = os.path.join(qdrant_path, "collection", "transcripts", "storage.sqlite")

    if not os.path.exists(sqlite_path):
        print(f"SQLite file not found: {sqlite_path}")
        return

    inspect_sqlite_file(sqlite_path)


if __name__ == "__main__":
    main()