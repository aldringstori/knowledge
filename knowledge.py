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
    single_video,
    single_short,
    channel_videos,
    channel_shorts,
    playlist,
    file_converter,
    summarize,
    channel_manager_ui
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
    elif '@' in url and '/shorts' in url:
        return 'channel_shorts'
    elif '@' in url or '/c/' in url or '/user/' in url or '/channel/' in url:
        return 'channel_videos'
    elif 'youtube.com/watch?v=' in url:
        return 'video'
    return None

def render_logs_tab():
    """Render the logs tab with most recent logs first"""
    st.header("System Logs")
    auto_refresh = st.checkbox("Auto-refresh logs", value=False)
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh", key="logs_tab_refresh"):
            st.rerun()
    with col2:
        if st.button("🗑️ Clear Logs", key="logs_tab_clear"):
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
        st.header("🔧 Browser Settings")
        
        # Initialize headless mode in session state if not exists
        if 'headless_mode' not in st.session_state:
            st.session_state.headless_mode = False
        
        # Headless mode toggle
        headless_mode = st.toggle(
            "Headless Mode", 
            value=st.session_state.headless_mode,
            help="Toggle browser visibility for Selenium operations"
        )
        
        # Update session state when toggle changes
        if headless_mode != st.session_state.headless_mode:
            st.session_state.headless_mode = headless_mode
            if headless_mode:
                st.success("🔒 Headless mode enabled - browser will be hidden")
            else:
                st.success("👁️ Headless mode disabled - browser will be visible")
        
        # Display current mode
        mode_text = "🔒 Hidden" if st.session_state.headless_mode else "👁️ Visible"
        st.caption(f"Browser mode: {mode_text}")
        
        st.divider()
        
        st.header("⏱️ Download Settings")
        
        # Download delay setting
        if 'download_delay' not in st.session_state:
            st.session_state.download_delay = 3
            
        download_delay = st.slider(
            "Download Delay (seconds)",
            min_value=1,
            max_value=10,
            value=st.session_state.download_delay,
            help="Delay between downloads to avoid overwhelming YouTube's servers"
        )
        
        # Update session state when slider changes
        if download_delay != st.session_state.download_delay:
            st.session_state.download_delay = download_delay
            st.success(f"⏱️ Download delay set to {download_delay} seconds")
        
        st.caption(f"Current delay: {st.session_state.download_delay}s between downloads")
        
        st.divider()
        
        st.header("🗄️ Playlist Cache Management")
        
        # Import cache here to avoid circular imports
        try:
            from utils.playlist_cache import PlaylistCache
            cache = PlaylistCache()
            cache_stats = cache.get_cache_stats()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Cached Playlists", cache_stats['total_playlists'])
                st.metric("Total Cached Videos", cache_stats['total_videos'])
            
            with col2:
                if st.button("🗑️ Clear All Cache", key="clear_all_cache"):
                    if cache.clear_cache():
                        st.success("All playlist cache cleared!")
                        st.rerun()
                    else:
                        st.error("Failed to clear cache")
                        
                if st.button("📊 Refresh Cache Stats", key="refresh_cache_stats"):
                    st.rerun()
            
            if cache_stats['oldest_cache'] and cache_stats['newest_cache']:
                st.caption(f"Cache range: {cache_stats['oldest_cache'][:10]} to {cache_stats['newest_cache'][:10]}")
                
        except ImportError:
            st.warning("Cache management not available")
        
        st.divider()
        
        st.header("📊 Logs & Monitoring")
        
        # Get available log files
        import os
        log_dir = "logs"
        available_logs = []
        if os.path.exists(log_dir):
            available_logs = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        
        col1, col2 = st.columns(2)
        
        with col1:
            log_file = st.selectbox(
                "Select Log File", 
                options=["Current Session"] + available_logs,
                help="Choose a specific log file to view"
            )
        
        with col2:
            max_lines = st.number_input(
                "Max Lines", 
                min_value=10, 
                max_value=1000, 
                value=100,
                help="Maximum number of recent lines to show"
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            if st.button("🔄 Refresh Logs", key="refresh_logs_btn"):
                if log_file == "Current Session":
                    logs = get_session_logs(max_lines=max_lines)
                    log_content = "\n".join(logs) if logs else ""
                else:
                    log_content = read_log_file(log_file, max_lines=max_lines)
                    log_content = "".join(log_content) if isinstance(log_content, list) else log_content
                
                if log_content.strip():
                    st.text_area("Log Output", log_content, height=400, key="log_display")
                else:
                    st.info("No logs available")
        
        with col4:
            if st.button("🗑️ Clear Logs", key="clear_logs_btn"):
                if log_file == "Current Session":
                    clear_session_logs()
                    st.success("Session logs cleared")
                else:
                    if clear_log_file(log_file):
                        st.success(f"Log file {log_file} cleared")
                    else:
                        st.error(f"Failed to clear log file {log_file}")
        
        # Show available log files info
        if available_logs:
            with st.expander("📄 Available Log Files", expanded=False):
                for log_file in available_logs:
                    file_path = os.path.join(log_dir, log_file)
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        size_mb = size / (1024 * 1024)
                        st.write(f"**{log_file}**: {size_mb:.2f} MB")
                    else:
                        st.write(f"**{log_file}**: File not found")

    config = get_config()
    # Add UI settings to config
    config['headless_mode'] = st.session_state.headless_mode
    config['download_delay_seconds'] = st.session_state.download_delay
    print("Loaded config in main - download_folder:", config.get('download_folder'))
    print("Loaded config in main - transcription_folder:", config.get('transcription_folder'))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Download",
        "Summarize", 
        "File Converter",
        "📺 Channels",
        "Logs"
    ])

    with tab1:
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

    with tab2:
        summarize.render(config)

    with tab3:
        st.header("File Converter")
        file_converter.render(config)

    with tab4:
        channel_manager_ui.render_channel_manager()

    with tab5:
        render_logs_tab()

    # Only save basic config data, not function objects
    try:
        basic_config = {k: v for k, v in config.items() if not callable(v)}
        save_config(basic_config)
        logger.info("Configuration saved.")
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")

if __name__ == "__main__":
    main()