# File: knowledge.py
import streamlit as st
import json
from datetime import datetime
import os
import time
import pandas as pd
import glob

from utils.logging_setup import (
    logger,
    get_session_logs,
    read_log_file,
    clear_log_file,
    clear_session_logs
)
from modules import (
    chat,
    single_video,
    single_short,
    channel_videos,
    channel_shorts,
    playlist,
    file_converter
)


def load_config():
    config_file = "settings.json"
    try:
        with open(config_file, 'r') as f:
            logger.info("Loading configuration from settings.json")
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Configuration file not found. Creating a new one with default settings.")
        config = {
            "download_folder": os.path.join(os.getcwd(), "Transcriptions"),
            "model_path": os.path.join(os.getcwd(), "models"),
            "qdrant_path": os.path.join(os.getcwd(), "qdrant_data")
        }
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return config


def save_config(config):
    config_file = "settings.json"
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
            logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")


def detect_url_type(url: str) -> str:
    """Detect the type of YouTube URL"""
    if not url:
        return None

    url = url.lower()
    if '/shorts/' in url:
        return 'short'
    elif '/playlist?' in url or '&list=' in url:
        return 'playlist'
    elif '@' in url and '/videos' in url:
        return 'channel_videos'
    elif '@' in url and '/shorts' in url:
        return 'channel_shorts'
    elif 'youtube.com/watch?v=' in url:
        return 'video'
    return None


def render_ingested_files_tab():
    """Render the ingested files tab"""
    st.header("Ingested Files")

    transcript_path = "/srv/knowledge/transcriptions"
    qdrant_path = "/srv/knowledge/qdrant_data"

    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Files"):
            st.rerun()
    with col2:
        if st.button("🗑️ Delete All Files"):
            try:
                # Clear transcripts directory
                files = glob.glob(os.path.join(transcript_path, "**/*.txt"), recursive=True)
                for f in files:
                    os.remove(f)
                # Clear Qdrant database
                if os.path.exists(qdrant_path):
                    for item in os.listdir(qdrant_path):
                        item_path = os.path.join(qdrant_path, item)
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                st.success("All files deleted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting files: {str(e)}")

    try:
        # Get all text files
        files = glob.glob(os.path.join(transcript_path, "**/*.txt"), recursive=True)

        if not files:
            st.info("No transcription files found.")
            return

        # Create a DataFrame to display files
        file_data = []
        total_size = 0

        for file_path in files:
            try:
                stat = os.stat(file_path)
                size_kb = round(stat.st_size / 1024, 2)
                total_size += size_kb

                # Read first line for title/content preview
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()[:50] + "..." if len(
                        f.readline().strip()) > 50 else f.readline().strip()

                file_data.append({
                    'Filename': os.path.basename(file_path),
                    'Preview': first_line,
                    'Size (KB)': size_kb,
                    'Modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'Path': os.path.relpath(file_path, transcript_path)
                })
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                continue

        if file_data:
            # Show summary
            st.info(f"Found {len(file_data)} files (Total size: {round(total_size / 1024, 2)} MB)")

            # Create DataFrame
            df = pd.DataFrame(file_data)

            # Display files in a table
            st.dataframe(
                df,
                column_config={
                    "Filename": st.column_config.TextColumn("Filename", width="medium"),
                    "Preview": st.column_config.TextColumn("Content Preview", width="large"),
                    "Size (KB)": st.column_config.NumberColumn("Size (KB)", format="%.2f"),
                    "Modified": st.column_config.TextColumn("Last Modified", width="medium"),
                    "Path": st.column_config.TextColumn("Path", width="medium")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("No files could be processed.")

    except Exception as e:
        st.error(f"Error reading ingested files: {str(e)}")
        logger.error(f"Error in ingested files tab: {str(e)}")


def render_logs_tab():
    """Render the logs tab with most recent logs first"""
    st.header("System Logs")

    # Add auto-refresh checkbox
    auto_refresh = st.checkbox("Auto-refresh logs", value=False)

    # Add manual refresh and clear buttons in the same row
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    with col2:
        if st.button("🗑️ Clear Logs"):
            try:
                # Clear the log file
                with open("knowledge.log", "w") as f:
                    f.write("")
                st.success("Logs cleared successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing logs: {str(e)}")

    try:
        # Read logs
        with open("knowledge.log", "r") as f:
            logs = f.readlines()

        if logs:
            # Reverse the logs to show newest first
            logs.reverse()

            # Join the reversed logs
            reversed_logs = ''.join(logs)

            # Display logs
            st.code(reversed_logs, language="text")

            # Show last update time
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("No logs available")

    except FileNotFoundError:
        st.info("No log file found")
    except Exception as e:
        st.error(f"Error reading logs: {str(e)}")

    # Add auto-refresh
    if auto_refresh:
        time.sleep(2)  # Wait 2 seconds
        st.rerun()


def main():
    st.title("YouTube Transcript Assistant")

    # Sidebar for logs
    with st.sidebar:
        st.header("Logs & Monitoring")
        log_type = st.radio("Select Log Type", ["Current Session", "Full Log History"])
        if st.button("Refresh Logs"):
            logs = get_session_logs() if log_type == "Current Session" else read_log_file()
            if logs.strip():
                st.text_area("Log Output", logs, height=400)
            else:
                st.info("No logs available")
        if st.button("Clear Logs"):
            if log_type == "Current Session":
                clear_session_logs()
                st.success("Session logs cleared")
            else:
                if clear_log_file():
                    st.success("Log file cleared")
                else:
                    st.error("Failed to clear log file")

    # Load configuration
    global config
    config = load_config()

    # Main content area with tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Chat",
        "Download",
        "File Converter",
        "Ingested Files",
        "Logs"
    ])

    with tab1:
        chat.render(config)

    with tab2:
        st.header("Download YouTube Content")
        url = st.text_input("Enter YouTube URL")
        process_button = st.button("Process and Download")

        if url and process_button:
            url_type = detect_url_type(url)

            if url_type:
                try:
                    status_container = st.empty()
                    progress_container = st.empty()

                    with st.spinner(f"Processing {url_type.replace('_', ' ').title()}..."):
                        status_container.info("Starting download process...")

                        if url_type == 'video':
                            single_video.render_url(url, config)
                        elif url_type == 'short':
                            single_short.render_url(url, config)
                        elif url_type == 'channel_videos':
                            channel_videos.render_url(url, config)
                        elif url_type == 'channel_shorts':
                            channel_shorts.render_url(url, config)
                        elif url_type == 'playlist':
                            playlist.render_url(url, config)

                        status_container.success("Processing completed! Check your downloads folder.")

                except Exception as e:
                    st.error(f"Error processing URL: {str(e)}")
                    logger.error(f"Error processing URL: {str(e)}")
            else:
                st.error("Invalid or unsupported YouTube URL")

    with tab3:
        st.header("File Converter")
        file_converter.render(config)

    with tab4:
        render_ingested_files_tab()

    with tab5:
        render_logs_tab()

    # Save config at the end
    save_config(config)
    logger.info("Configuration saved.")


if __name__ == "__main__":
    main()