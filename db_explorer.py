#!/usr/bin/env python3
"""
Database explorer for Qdrant SQLite database
"""
import os
import json
import sqlite3
import sys
import base64
import pprint


def explore_database(sqlite_path):
    """Explore the contents of the Qdrant SQLite database"""
    if not os.path.exists(sqlite_path):
        print(f"Database file not found: {sqlite_path}")
        return

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in database: {tables}")

    # Check points table
    if ('points',) in tables:
        # Get columns
        cursor.execute("PRAGMA table_info(points);")
        columns = cursor.fetchall()
        print("\nPoints table columns:")
        for col in columns:
            print(f"  {col}")

        # Get row count
        cursor.execute("SELECT COUNT(*) FROM points;")
        count = cursor.fetchone()[0]
        print(f"\nNumber of points: {count}")

        if count > 0:
            # Get one row to examine
            cursor.execute("SELECT * FROM points LIMIT 1;")
            sample_row = cursor.fetchone()
            print("\nSample row structure:")
            for i, col in enumerate(columns):
                col_name = col[1]
                value = sample_row[i]
                print(f"  {col_name}: {type(value)}")

                # Try to interpret the data
                if col_name == 'point' and isinstance(value, (bytes, str)):
                    print("  Attempting to decode point data...")
                    try:
                        if isinstance(value, bytes):
                            data = value.decode('utf-8')
                        else:
                            data = value

                        # Try to parse as JSON
                        try:
                            parsed = json.loads(data)
                            print("  Decoded as JSON:")
                            pprint.pprint(parsed, indent=4, width=100, depth=2)
                        except:
                            # If not JSON, print the first 200 chars
                            print(f"  Raw data (first 200 chars): {data[:200]}")
                    except:
                        print("  Could not decode as UTF-8, printing as hex")
                        if isinstance(value, bytes):
                            print(f"  Hex: {value.hex()[:100]}...")

            # Examine a few more rows
            print("\nExamining a few more point IDs:")
            cursor.execute("SELECT id FROM points ORDER BY id LIMIT 5;")
            ids = [row[0] for row in cursor.fetchall()]
            print(f"  Point IDs: {ids}")

    conn.close()


def main():
    """Main function to explore database"""
    # Get path from settings.json or command line
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

    print(f"Exploring database: {sqlite_path}")
    explore_database(sqlite_path)


if __name__ == "__main__":
    main()