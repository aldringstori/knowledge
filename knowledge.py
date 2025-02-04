import streamlit as st
import os
import json
from datetime import datetime
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
from transformers import GPT2Tokenizer


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

    # Initialize tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or '[PAD]'

    # Main content area with tabs
    tab1, tab2, tab3 = st.tabs(["Chat", "Download", "File Converter"])

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

    # Save config at the end
    save_config(config)
    logger.info("Configuration saved.")


if __name__ == "__main__":
    main()