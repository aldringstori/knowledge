import streamlit as st
from utils.logging_setup import logger
from utils.common import create_folder, sanitize_filename, save_transcript_to_text
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
import time
import re
import os


def get_channel_name_from_shorts_url(shorts_url):
    """Extract channel name from shorts URL."""
    match = re.search(r"youtube\.com/[@]?([^/]+)/shorts", shorts_url)
    if match:
        return match.group(1)
    else:
        return "UnknownChannel"


def fetch_shorts_transcript(shorts_url):
    """Fetch transcript for a shorts video."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    shorts_url = shorts_url.replace("/shorts/", "/watch?v=")
    match = re.search(r"v=([a-zA-Z0-9_-]{11})", shorts_url)
    if match is None:
        return None, "Could not find a valid video ID in the URL."

    video_id = match.group(1)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return transcript, None
    except NoTranscriptFound:
        return None, "No transcript found for the provided video ID."
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."


def fetch_videos_from_shorts_page(shorts_url):
    """Fetch all shorts videos from a channel."""
    options = FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.get(shorts_url)
    time.sleep(5)

    last_height = driver.execute_script("return document.documentElement.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    videos_data = []
    videos = driver.find_elements(By.CSS_SELECTOR, "a.yt-simple-endpoint.style-scope.ytd-rich-grid-slim-media")
    for video in videos:
        href = video.get_attribute('href')
        title_element = video.find_element(By.ID, "video-title")
        title = title_element.text if title_element else "Unknown Title"
        videos_data.append((href, title))

    driver.quit()
    return videos_data


def download_all_shorts_transcripts(shorts_url, config):
    """Download transcripts for all shorts in a channel."""
    st.info(f"Starting download process for shorts from URL: {shorts_url}")
    logger.info(f"Starting download process for shorts from URL: {shorts_url}")

    channel_name = get_channel_name_from_shorts_url(shorts_url)
    if not channel_name:
        logger.error("Could not extract channel name from URL.")
        st.error("Could not extract channel name from URL. Please check the URL and try again.")
        return

    folder_name = os.path.join(config['download_folder'], channel_name)
    st.info(f"Downloading transcripts to folder: {folder_name}")
    logger.info(f"Downloading transcripts to folder: {folder_name}")
    create_folder(folder_name)

    shorts_data = fetch_videos_from_shorts_page(shorts_url)
    st.info(f"Found {len(shorts_data)} shorts to process.")
    logger.info(f"Found {len(shorts_data)} shorts to process.")

    if not shorts_data:
        logger.error("No shorts data found after fetching the page.")
        st.error("No shorts data found after fetching the page. Please check the URL and try again.")
        return

    progress_bar = st.progress(0)
    for i, (url, title) in enumerate(shorts_data):
        sanitized_title = sanitize_filename(title)
        st.info(f"Processing short: {sanitized_title}")
        logger.info(f"Processing short: {sanitized_title}")

        video_url = f"https://www.youtube.com{url}"

        try:
            transcript, error = fetch_shorts_transcript(video_url)
            if error:
                logger.warning(f"Error downloading transcript for {sanitized_title}: {error}")
                st.warning(f"Error downloading transcript for {sanitized_title}: {error}")
                continue
            if not transcript:
                logger.warning(f"No transcript available for {sanitized_title}.")
                st.warning(f"No transcript available for {sanitized_title}.")
                continue

            save_path = save_transcript_to_text(
                ' '.join([entry['text'] for entry in transcript]),
                sanitized_title,
                folder_name
            )
            st.success(f"Transcript for {sanitized_title} saved to {save_path}.")
            logger.info(f"Transcript for {sanitized_title} saved to {save_path}.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {sanitized_title}: {str(e)}")
            st.error(f"An unexpected error occurred while processing {sanitized_title}: {str(e)}")

        progress_bar.progress((i + 1) / len(shorts_data))

    st.success("All available shorts transcripts have been downloaded.")
    logger.info("All available shorts transcripts have been downloaded.")


def render(config):
    """Render the channel shorts tab."""
    st.header("Channel Shorts Transcripts")
    shorts_channel_url = st.text_input("Enter YouTube Shorts Channel URL:")

    if st.button("Download All Channel Shorts Transcripts"):
        if shorts_channel_url:
            with st.spinner("Downloading transcripts from shorts channel..."):
                logger.info(f"Downloading transcripts from shorts channel URL: {shorts_channel_url}")
                download_all_shorts_transcripts(shorts_channel_url, config)
        else:
            st.warning("Please enter a valid YouTube Shorts Channel URL.")
            logger.warning("No YouTube Shorts Channel URL entered.")