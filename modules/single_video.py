import streamlit as st
from utils.logging_setup import logger
from utils.common import get_video_title, fetch_transcript, save_transcript_to_text


def render(config):
    """
    Render the single video transcript tab
    """
    st.header("Single Video Transcript")
    video_url = st.text_input("Enter YouTube Video URL:")

    if st.button("Download Transcript"):
        if video_url:
            with st.spinner("Downloading transcript..."):
                logger.info(f"Downloading transcript for video URL: {video_url}")
                transcript = fetch_transcript(video_url)
                if transcript:
                    filename = get_video_title(video_url)
                    save_path = save_transcript_to_text(transcript, filename, config['download_folder'])
                    if save_path:
                        st.success(f"Transcript saved to {save_path}")
                        logger.info(f"Transcript saved to {save_path}")
                    else:
                        st.error("Failed to save the transcript.")
                        logger.error("Failed to save the transcript.")
                else:
                    st.error("Failed to fetch transcript.")
                    logger.error("Failed to fetch transcript.")
        else:
            st.warning("Please enter a valid YouTube URL.")
            logger.warning("No YouTube URL entered.")