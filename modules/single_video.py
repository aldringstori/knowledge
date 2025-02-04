import streamlit as st
from utils.logging_setup import logger
from utils.common import get_video_title, fetch_transcript, save_transcript_to_text


def render_url(video_url: str, config: dict):
    """Process a single video URL"""
    try:
        logger.info(f"Processing video URL: {video_url}")
        transcript = fetch_transcript(video_url)

        if transcript:
            filename = get_video_title(video_url)
            save_path = save_transcript_to_text(transcript, filename, config['download_folder'])
            if save_path:
                st.success(f"Transcript saved to {save_path}")
                logger.info(f"Transcript saved to {save_path}")
                return True
            else:
                st.error("Failed to save transcript")
                logger.error("Failed to save transcript")
        else:
            st.error("No transcript available for this video")
            logger.error("Failed to fetch transcript")
        return False
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        st.error(f"Error processing video: {str(e)}")
        return False


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