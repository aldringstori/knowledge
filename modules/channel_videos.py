import streamlit as st
import pandas as pd
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url
)
from utils.table_utils import render_with_progress
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
import os
import re
import time


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
    """Extract channel name from URL"""
    match = re.search(r'youtube\.com/[@]?([^/]+)/?', url)
    return match.group(1) if match else "UnknownChannel"


def fetch_channel_videos(channel_url):
    """Fetch all videos from a channel using Selenium"""
    driver = None
    try:
        driver = setup_chrome_driver()
        driver.get(channel_url)
        time.sleep(5)

        # Scroll to load more videos
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Find video elements
        videos = driver.find_elements(By.CSS_SELECTOR, "a#video-title-link")
        video_data = []

        for video in videos:
            try:
                url = video.get_attribute('href')
                title = video.get_attribute('title')
                if url and title and 'watch?v=' in url:
                    video_data.append({
                        'url': url,
                        'title': sanitize_filename(title)
                    })
            except Exception as e:
                logger.error(f"Error processing video element: {str(e)}")
                continue

        if driver:
            driver.quit()
        return video_data
    except Exception as e:
        if driver:
            driver.quit()
        logger.error(f"Error fetching channel videos: {str(e)}")
        raise


def render_url(channel_url: str, config: dict):
    """Process a channel URL - maintained for backward compatibility"""
    config['name_extractor'] = get_channel_name
    return render_with_progress(
        fetch_channel_videos,
        channel_url,
        config,
        item_type='video'
    )


def render(config):
    """Render method for channel videos"""
    st.header("Channel Videos Transcripts")
    channel_url = st.text_input("Enter YouTube Channel URL:")

    if st.button("Download Channel Transcripts"):
        if channel_url:
            with st.spinner("Downloading channel transcripts..."):
                render_url(channel_url, config)
        else:
            st.warning("Please enter a valid YouTube Channel URL.")