import streamlit as st
from utils.logging_setup import logger
from utils.common import (
    sanitize_filename,
    save_transcript_to_text,
    get_video_id_from_url
)
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled
)
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import time


def get_video_title_selenium(video_url):
    """Get video title using Selenium"""
    try:
        options = FirefoxOptions()
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)
        driver.get(video_url)
        time.sleep(2)
        title = driver.title
        if " - YouTube" in title:
            title = title.replace(" - YouTube", "")
        driver.quit()
        return sanitize_filename(title)
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
        video_title = get_video_title_selenium(shorts_url)
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