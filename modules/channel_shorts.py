import streamlit as st
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    save_transcript_to_text,
    get_video_id_from_url
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled
)
import time
import os
import re


def setup_chrome_driver():
    """Setup Chrome WebDriver with proper configuration"""
    try:
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        service = ChromeService(log_output=os.path.devnull)
        return webdriver.Chrome(options=options, service=service)
    except Exception as e:
        logger.error(f"Chrome WebDriver setup failed: {str(e)}")
        raise


def get_channel_name(url):
    """Extract channel name from shorts URL"""
    match = re.search(r'youtube\.com/[@]?([^/]+)/?', url)
    return match.group(1) if match else "UnknownChannel"


def fetch_channel_shorts(channel_url):
    """Fetch all shorts from a channel using Selenium"""
    driver = None
    try:
        driver = setup_chrome_driver()
        driver.get(channel_url)
        time.sleep(5)

        # Scroll to load more shorts
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Find shorts elements
        shorts = driver.find_elements(By.CSS_SELECTOR, "a.ytd-rich-grid-slim-media")
        shorts_data = []

        for short in shorts:
            try:
                url = short.get_attribute('href')
                title = short.get_attribute('title')
                if url and title and '/shorts/' in url:
                    shorts_data.append({
                        'url': url,
                        'title': sanitize_filename(title)
                    })
            except Exception as e:
                logger.error(f"Error processing short element: {str(e)}")
                continue

        driver.quit()
        return shorts_data
    except Exception as e:
        if driver:
            driver.quit()
        logger.error(f"Error fetching channel shorts: {str(e)}")
        raise


def fetch_short_transcript(short_url):
    """Fetch transcript for a single short"""
    short_url = short_url.replace("/shorts/", "/watch?v=")
    video_id = get_video_id_from_url(short_url)

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


def render_url(channel_url: str, config: dict):
    """Process a channel shorts URL"""
    try:
        channel_name = get_channel_name(channel_url)
        folder_name = os.path.join(config['download_folder'], f"{channel_name}_shorts")
        create_folder(folder_name)

        shorts = fetch_channel_shorts(channel_url)
        if not shorts:
            st.error("No shorts found in channel")
            return False

        st.info(f"Found {len(shorts)} shorts in channel")
        progress_bar = st.progress(0)

        successful = 0
        for i, short in enumerate(shorts):
            try:
                transcript, error = fetch_short_transcript(short['url'])
                if transcript and not error:
                    text = ' '.join([entry['text'] for entry in transcript])
                    save_path = save_transcript_to_text(
                        text,
                        short['title'],
                        folder_name
                    )
                    if save_path:
                        successful += 1
                progress_bar.progress((i + 1) / len(shorts))
            except Exception as e:
                logger.error(f"Error processing short {short['title']}: {str(e)}")
                continue

        if successful > 0:
            st.success(f"Successfully downloaded {successful} out of {len(shorts)} transcripts to {folder_name}")
            return True
        else:
            st.error("Failed to download any transcripts")
            return False

    except Exception as e:
        logger.error(f"Error processing channel shorts: {str(e)}")
        st.error(f"Error processing channel shorts: {str(e)}")
        return False


def render(config):
    """Legacy render method for backward compatibility"""
    st.header("Channel Shorts Transcripts")
    channel_url = st.text_input("Enter YouTube Channel Shorts URL:")
    if st.button("Download Channel Shorts"):
        if channel_url:
            with st.spinner("Downloading channel shorts..."):
                render_url(channel_url, config)
        else:
            st.warning("Please enter a valid YouTube Channel Shorts URL.")