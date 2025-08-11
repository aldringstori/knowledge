import streamlit as st
import os
from utils.logging_setup import get_single_short_logger
from utils.video_database import is_video_already_downloaded, mark_video_as_downloaded, get_video_database

# Get module-specific logger
logger = get_single_short_logger()
from utils.common import (
    sanitize_filename,
    save_transcript_to_text,
    get_video_id_from_url,
    get_video_title
)
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled
)
import time


def get_video_title_for_short(video_url):
    """Get video title for shorts using the common function"""
    try:
        title = get_video_title(video_url)
        return title if title else f"short_{get_video_id_from_url(video_url)}"
    except Exception as e:
        logger.error(f"Error fetching video title: {str(e)}")
        video_id = get_video_id_from_url(video_url)
        return f"short_{video_id}"


def fetch_shorts_transcript(shorts_url):
    """Fetch transcript for a shorts video"""
    shorts_url = shorts_url.replace("/shorts/", "/watch?v=")
    video_id = get_video_id_from_url(shorts_url)

    if not video_id:
        return None, "Invalid video ID"

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return transcript, None
    except NoTranscriptFound:
        return None, "No transcript available"
    except TranscriptsDisabled:
        return None, "Transcripts are disabled"
    except Exception as e:
        return None, str(e)


def render_url(shorts_url: str, config: dict):
    """Process a single short URL"""
    try:
        logger.info(f"Processing shorts URL: {shorts_url}")
        
        # Check if video was already downloaded
        if is_video_already_downloaded(shorts_url):
            db = get_video_database()
            existing_video = db.get_downloaded_video(shorts_url)
            
            if existing_video:
                # Check if the file still exists
                if existing_video.get('file_path') and os.path.exists(existing_video['file_path']):
                    st.info(f"✅ Video already downloaded: {existing_video.get('title', 'Unknown')}")
                    st.info(f"📁 File location: {existing_video['file_path']}")
                    logger.info(f"Skipping already downloaded short: {shorts_url}")
                    
                    # Update the database with current timestamp
                    mark_video_as_downloaded(
                        shorts_url, 
                        existing_video.get('title'),
                        existing_video['file_path'],
                        existing_video.get('duration'),
                        config.get('source_type', 'single'),
                        config.get('source_url')
                    )
                    
                    return True
                else:
                    logger.info(f"Existing transcript file not found, re-downloading: {shorts_url}")
                    # Remove the orphaned database entry
                    db.remove_video(shorts_url)
        
        video_title = get_video_title_for_short(shorts_url)
        transcript, error = fetch_shorts_transcript(shorts_url)

        if error:
            st.error(error)
            logger.error(error)
            return False

        if transcript:
            text = ' '.join([entry['text'] for entry in transcript])
            save_path = save_transcript_to_text(text, video_title, config['download_folder'])

            if save_path:
                st.success(f"Transcript saved to {save_path}")
                logger.info(f"Transcript saved to {save_path}")
                
                # Mark video as downloaded in database
                try:
                    mark_video_as_downloaded(
                        shorts_url,
                        video_title,
                        save_path,
                        duration=None,  # Duration not available in this context
                        source_type=config.get('source_type', 'single'),
                        source_url=config.get('source_url')
                    )
                    logger.info(f"Short marked as downloaded in database: {video_title}")
                except Exception as e:
                    logger.warning(f"Could not mark short as downloaded in database: {e}")
                
                return True
            else:
                st.error("Failed to save transcript")
                logger.error("Failed to save transcript")
        else:
            st.error("No transcript available")
            logger.error("No transcript available")
        return False
    except Exception as e:
        logger.error(f"Error processing short: {str(e)}")
        st.error(f"Error processing short: {str(e)}")
        return False


def render(config):
    """Legacy render method for backward compatibility"""
    st.header("Single Short Transcript")
    shorts_url = st.text_input("Enter YouTube Shorts URL:")
    if st.button("Download Transcript"):
        if shorts_url:
            with st.spinner("Downloading transcript..."):
                render_url(shorts_url, config)
        else:
            st.warning("Please enter a valid YouTube Shorts URL.")