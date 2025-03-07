import streamlit as st
from datetime import datetime
import time
import os

from utils.logging_setup import (
    logger,
    get_session_logs,
    read_log_file,
    clear_log_file,
    clear_session_logs
)
from utils.config import (
    get_config,
    save_config,
    update_config,
    delete_files,
    get_transcript_files
)
from modules import (
    chat,
    single_video,
    single_short,
    channel_videos,
    channel_shorts,
    playlist,
    file_converter,
    summarize  # Import the new summarize module
)

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

    # Load configuration
    config = get_config()
    transcript_path = config.get("download_folder")
    qdrant_path = config.get("qdrant_path")

    # Verify paths exist
    if not all([transcript_path, qdrant_path]):
        st.error("Configuration error: Missing required paths. Please check settings.json")
        return

    # Add refresh and delete buttons
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Files"):
            st.rerun()

    with col2:
        if st.button("🗑️ Delete All Files"):
            success, message = delete_files()
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    # Display current files
    files = get_transcript_files()
    if files:
        st.subheader("Current Transcription Files:")
        for f in files:
            st.text(os.path.relpath(f, transcript_path))
    else:
        st.info("No transcription files found.")

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
    config = get_config()

    # Main content area with tabs - added the new Summarize tab
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Chat",
        "Download",
        "Summarize",  # New tab
        "File Converter",
        "Ingested Files",
        "Logs"
    ])

    with tab1:
        chat.render(config)

    with tab2:
        st.header("Download YouTube Content")
        url = st.text_input("Enter YouTube URL", key="download_url")
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
        # Render the summarize tab using the module
        summarize.render(config)

    with tab4:
        st.header("File Converter")
        file_converter.render(config)

    with tab5:
        render_ingested_files_tab()

    with tab6:
        render_logs_tab()

    # Save any changes to config
    save_config(config)
    logger.info("Configuration saved.")

if __name__ == "__main__":
    main()