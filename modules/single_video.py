import streamlit as st
import os
from utils.logging_setup import get_single_video_logger
from utils.channel_manager import ChannelManager
from utils.video_database import is_video_already_downloaded, mark_video_as_downloaded, get_video_database

# Get module-specific logger
logger = get_single_video_logger()
from utils.common import get_video_title, fetch_transcript, save_transcript_to_text


def render_url(video_url: str, config: dict):
    """Process a single video URL and return transcript, filename, and error status."""
    transcript_text = None
    output_filename = None
    error_message = None
    try:
        logger.info(f"Processing video URL: {video_url}")
        
        # Check if video was already downloaded
        if is_video_already_downloaded(video_url):
            db = get_video_database()
            existing_video = db.get_downloaded_video(video_url)
            
            if existing_video:
                # Check if the file still exists
                if existing_video.get('file_path') and os.path.exists(existing_video['file_path']):
                    st.info(f"✅ Video already downloaded: {existing_video.get('title', 'Unknown')}")
                    st.info(f"📁 File location: {existing_video['file_path']}")
                    logger.info(f"Skipping already downloaded video: {video_url}")
                    
                    # Return the existing file information
                    try:
                        with open(existing_video['file_path'], 'r', encoding='utf-8') as f:
                            transcript_text = f.read()
                        output_filename = existing_video['file_path']
                        
                        # Update the database with current timestamp
                        mark_video_as_downloaded(
                            video_url, 
                            existing_video.get('title'),
                            existing_video['file_path'],
                            existing_video.get('duration'),
                            config.get('source_type', 'single'),
                            config.get('source_url')
                        )
                        
                        return transcript_text, output_filename, None
                    except Exception as e:
                        logger.warning(f"Could not read existing transcript file: {e}")
                        # Continue with normal download process
                else:
                    logger.info(f"Existing transcript file not found, re-downloading: {video_url}")
                    # Remove the orphaned database entry
                    db.remove_video(video_url)
        
        headless_mode = config.get('headless_mode', False)
        transcript_text = fetch_transcript(video_url, headless=headless_mode)

        if transcript_text:
            video_title = get_video_title(video_url, headless=headless_mode) # Use the actual video title for the filename
            # Use output_filename_prefix from config if available, otherwise use video_title
            filename_prefix = config.get('output_filename_prefix', video_title)
            output_filename = save_transcript_to_text(transcript_text, filename_prefix, config.get('output_path', config['download_folder']))
            
            if output_filename:
                st.success(f"Transcript saved to {output_filename}")
                logger.info(f"Transcript saved to {output_filename}")
                
                # Mark video as downloaded in database
                try:
                    mark_video_as_downloaded(
                        video_url,
                        video_title,
                        output_filename,
                        duration=None,  # Duration not available in this context
                        source_type=config.get('source_type', 'single'),
                        source_url=config.get('source_url')
                    )
                    logger.info(f"Video marked as downloaded in database: {video_title}")
                except Exception as e:
                    logger.warning(f"Could not mark video as downloaded in database: {e}")
                
                # Track video download if it's from a monitored channel
                try:
                    cm = ChannelManager()
                    if cm.track_video_download(video_url, video_title, output_filename):
                        logger.info(f"Video tracked for channel management: {video_title}")
                except Exception as e:
                    logger.warning(f"Could not track video for channel management: {e}")
                    
            else:
                error_message = "Failed to save transcript"
                st.error(error_message)
                logger.error(error_message)
        else:
            error_message = "No transcript available for this video"
            st.error(error_message)
            logger.error(error_message)
        
    except Exception as e:
        error_message = f"Error processing video: {str(e)}"
        logger.error(error_message)
        st.error(error_message)
        # Ensure transcript_text is None if an error occurred before or during fetching
        transcript_text = None 
        output_filename = None

    return transcript_text, output_filename, error_message


def render(config):
    """Legacy render method for backward compatibility"""
    st.header("Single Video Transcript")
    video_url = st.text_input("Enter YouTube Video URL:")
    if st.button("Download Transcript"):
        if video_url:
            with st.spinner("Downloading transcript..."):
                render_url(video_url, config)
        else:
            st.warning("Please enter a valid YouTube URL.")
