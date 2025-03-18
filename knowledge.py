"""
YouTube Transcript Assistant - Main application file
"""
import sys
import os

# Add the current directory to the path to find our patches
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Apply both patches before any other imports
try:
    # Try to import huggingface_hub directly first to make sure it's patched
    # before any other modules try to import from it
    import huggingface_hub
except ImportError:
    print("Note: huggingface_hub not imported yet")

try:
    # Apply the huggingface_hub patch
    from huggingface_patch import *
except ImportError:
    print("Warning: huggingface_patch.py not found. You may encounter import errors.")

try:
    # Apply the transformers patch
    from transformers_patch import *
except ImportError:
    print("Warning: transformers_patch.py not found. You may encounter import errors.")

# Now continue with your regular imports
import streamlit as st
from datetime import datetime
import time

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
    summarize,
    model_comparison,
    data_treatment,
    ai_blog
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

def render_logs_tab():
    """Render the logs tab with most recent logs first"""
    st.header("System Logs")
    auto_refresh = st.checkbox("Auto-refresh logs", value=False)
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    with col2:
        if st.button("🗑️ Clear Logs"):
            try:
                with open("knowledge.log", "w") as f:
                    f.write("")
                st.success("Logs cleared successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing logs: {str(e)}")
    try:
        with open("knowledge.log", "r") as f:
            logs = f.readlines()
        if logs:
            logs.reverse()
            reversed_logs = ''.join(logs)
            st.code(reversed_logs, language="text")
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-% k:%M:%S')}")
        else:
            st.info("No logs available")
    except FileNotFoundError:
        st.info("No log file found")
    except Exception as e:
        st.error(f"Error reading logs: {str(e)}")
    if auto_refresh:
        time.sleep(2)
        st.rerun()

def main():
    st.title("YouTube Transcript Assistant")

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

    config = get_config()
    print("Loaded config in main:", config)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Chat",
        "Download",
        "Summarize",
        "File Converter",
        "Data Treatment",
        "Logs",
        "Model Comparison",
        "AI Blog"
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
        summarize.render(config)

    with tab4:
        st.header("File Converter")
        file_converter.render(config)

    with tab5:
        data_treatment.render(config)

    with tab6:
        render_logs_tab()

    with tab7:
        model_comparison.render(config)

    with tab8:
        ai_blog.render(config)

    save_config(config)
    logger.info("Configuration saved.")

if __name__ == "__main__":
    main()