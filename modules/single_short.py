import streamlit as st
from utils.logging_setup import logger
from utils.common import sanitize_filename, save_transcript_to_text, get_video_id_from_url
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium import webdriver
import time
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def get_video_title_selenium(video_url):
    """Get video title using Selenium."""
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
        logger.error(f"Error fetching video title with Selenium: {str(e)}")
        video_id = get_video_id_from_url(video_url)
        return f"video_{video_id}"


def fetch_shorts_title_and_transcript(shorts_url):
    """Handle shorts title and transcript fetching."""
    shorts_url = shorts_url.replace("/shorts/", "/watch?v=")
    video_id = get_video_id_from_url(shorts_url)

    if not video_id:
        return None, None, "Invalid video ID"

    title = get_video_title_selenium(shorts_url)

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return title, transcript, None
    except NoTranscriptFound:
        return title, None, "No transcript found"
    except TranscriptsDisabled:
        return title, None, "Transcripts are disabled"
    except Exception as e:
        return title, None, str(e)


def render(config):
    """Render the single short transcript tab."""
    st.header("Single YouTube Short Transcript")
    shorts_url = st.text_input("Enter YouTube Shorts URL:")

    if st.button("Download Short Transcript"):
        if shorts_url:
            with st.spinner("Downloading shorts transcript..."):
                logger.info(f"Downloading transcript for shorts URL: {shorts_url}")
                title, transcript, error = fetch_shorts_title_and_transcript(shorts_url)

                if error:
                    st.error(error)
                    logger.error(error)
                elif transcript:
                    save_path = save_transcript_to_text(
                        ' '.join([entry['text'] for entry in transcript]),
                        title,
                        config['download_folder']
                    )
                    if save_path:
                        st.success(f"Short transcript saved to {save_path}")
                        logger.info(f"Short transcript saved to {save_path}")
                    else:
                        st.error("Failed to save the short transcript.")
                        logger.error("Failed to save the short transcript.")
                else:
                    st.error("Failed to fetch short transcript.")
                    logger.error("Failed to fetch short transcript.")
        else:
            st.warning("Please enter a valid YouTube Shorts URL.")
            logger.warning("No YouTube Shorts URL entered.")