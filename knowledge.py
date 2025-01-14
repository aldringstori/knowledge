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
    chat,  # New chat module
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
            "model_path": os.path.join(os.getcwd(), "models"),  # Path for saving model weights
            "qdrant_path": os.path.join(os.getcwd(), "qdrant_data")  # Path for Qdrant storage
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

def main():
    st.title("YouTube Transcript Assistant")

    # Sidebar for logs
    with st.sidebar:
        st.header("Logs & Monitoring")
        log_type = st.radio(
            "Select Log Type",
            ["Current Session", "Full Log History"]
        )
        if st.button("Refresh Logs"):
            if log_type == "Current Session":
                logs = get_session_logs()
            else:
                logs = read_log_file()
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

    # Ensure tokenizer has a padding token and eos token
    if tokenizer.pad_token is None:
        if tokenizer.eos_token is None:
            tokenizer.add_special_tokens({'pad_token': '[PAD]', 'eos_token': '[EOS]'})
        else:
            tokenizer.pad_token = tokenizer.eos_token

    # Main content area
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Chat",  # New chat tab
        "Single Video",
        "Single Short",
        "Channel Videos",
        "Channel Shorts",
        "Playlist",
        "File Converter"
    ])

    with tab1:
        chat.render(config)
    with tab2:
        single_video.render(config)
    with tab3:
        single_short.render(config)
    with tab4:
        channel_videos.render(config)
    with tab5:
        channel_shorts.render(config)
    with tab6:
        playlist.render(config)
    with tab7:
        file_converter.render(config)

    # Save config at the end
    save_config(config)
    logger.info("Configuration saved.")

if __name__ == "__main__":
    main()
