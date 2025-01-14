import streamlit as st
import pandas as pd
from utils.logging_setup import logger
from utils.common import (
    get_video_id_from_url,
    get_video_title,
    fetch_transcript,
    save_transcript_to_text,
    create_folder
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import re
import os


def setup_chrome_driver():
    """Setup Chrome WebDriver with proper configuration."""
    try:
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')

        # Create service with no log output
        service = ChromeService(
            log_output=os.path.devnull
        )

        driver = webdriver.Chrome(
            options=options,
            service=service
        )
        return driver
    except WebDriverException as e:
        logger.error(f"WebDriver setup failed: {str(e)}")
        raise Exception(
            "Failed to initialize Chrome WebDriver. Please make sure Chrome is properly installed."
        )
    except Exception as e:
        logger.error(f"Unexpected error in WebDriver setup: {str(e)}")
        raise


def get_channel_name_from_url(channel_url):
    """Extract channel name from URL."""
    match = re.search(r'youtube\.com/[@]?([^/]+)/?', channel_url)
    if match:
        channel_name = match.group(1)
        logger.info(f"Extracted channel name from URL: {channel_name}")
        return channel_name
    else:
        logger.error("Could not extract channel name from URL.")
        return None


def fetch_videos_from_channel_selenium(channel_url):
    """Fetch videos from channel using Selenium with Chrome."""
    driver = None
    try:
        logger.info("Setting up Chrome WebDriver...")
        driver = setup_chrome_driver()
        wait = WebDriverWait(driver, 20)

        logger.info(f"Loading channel URL: {channel_url}")
        driver.get(channel_url)
        time.sleep(5)

        # Scroll with timeout
        scroll_timeout = 120  # 2 minutes
        scroll_pause_time = 2
        scroll_start_time = time.time()

        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(scroll_pause_time)

            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                logger.info("Reached end of channel page")
                break

            if time.time() - scroll_start_time > scroll_timeout:
                logger.warning("Scroll timeout reached")
                break

            last_height = new_height

        # Try multiple selectors for video elements
        video_selectors = [
            "a#video-title-link",  # Main video title links
            "a#video-title",  # Alternative title links
            "ytd-grid-video-renderer a#thumbnail"  # Grid view thumbnails
        ]

        videos_data = []
        for selector in video_selectors:
            try:
                logger.info(f"Trying to find videos with selector: {selector}")
                videos = driver.find_elements(By.CSS_SELECTOR, selector)

                if videos:
                    logger.info(f"Found {len(videos)} videos with selector {selector}")
                    for video in videos:
                        try:
                            video_url = video.get_attribute('href')
                            video_title = video.get_attribute('title')

                            if not video_title:
                                video_title = video.text

                            if not video_title:
                                video_title = video.get_attribute('aria-label')

                            if video_url and video_title and 'watch?v=' in video_url:
                                sanitized_title = re.sub(r'[\\/*?:"<>|]', '', video_title)
                                video_data = (video_url, sanitized_title)
                                if video_data not in videos_data:
                                    videos_data.append(video_data)
                                    logger.info(f"Added video: {sanitized_title}")

                        except Exception as e:
                            logger.error(f"Error processing video element: {str(e)}")
                            continue

                    if videos_data:
                        break  # Found videos with this selector, stop trying others

            except Exception as e:
                logger.error(f"Error with selector {selector}: {str(e)}")
                continue

        if driver:
            driver.quit()

        logger.info(f"Found total of {len(videos_data)} videos")
        return videos_data

    except Exception as e:
        logger.error(f"Error in fetch_videos_from_channel_selenium: {str(e)}")
        if driver:
            driver.quit()
        raise


def render(config):
    """Render the channel videos tab."""
    st.header("Channel Videos Transcripts")
    channel_url = st.text_input("Enter YouTube Channel URL:")

    if st.button("Fetch Channel Videos"):
        if channel_url:
            try:
                with st.spinner("Fetching videos from channel..."):
                    logger.info(f"Fetching videos from channel URL: {channel_url}")
                    status_placeholder = st.empty()
                    status_placeholder.info("Loading channel data... This may take a few moments.")

                    channel_name = get_channel_name_from_url(channel_url)
                    if not channel_name:
                        st.error("Could not extract channel name from URL.")
                        logger.error("Could not extract channel name from URL.")
                        return

                    folder_name = os.path.join(config['download_folder'], channel_name)
                    create_folder(folder_name)

                    videos_data = fetch_videos_from_channel_selenium(channel_url)

                    if videos_data:
                        status_placeholder.success(f"Found {len(videos_data)} videos")

                        # Prepare the table data
                        video_list = []
                        for idx, (video_url, video_title) in enumerate(videos_data, start=1):
                            video_id = get_video_id_from_url(video_url)
                            video_list.append({
                                'ID': idx,
                                'Video Title': video_title,
                                'Video ID': video_id,
                                'Downloaded': ''
                            })
                        # Store in session state
                        st.session_state['video_list'] = video_list
                        st.session_state['videos_data'] = videos_data
                        st.session_state['folder_name'] = folder_name
                    else:
                        st.warning("No videos found or unable to process the channel URL.")
                        logger.warning("No videos found or unable to process the channel URL.")
            except Exception as e:
                logger.error(f"Error fetching channel videos: {str(e)}")
                st.error(f"Error fetching channel videos: {str(e)}")
        else:
            st.warning("Please enter a valid YouTube Channel URL.")
            logger.warning("No YouTube Channel URL entered.")

    # Display the table if video_list exists
    if 'video_list' in st.session_state:
        video_list = st.session_state['video_list']
        df = pd.DataFrame(video_list)
        table_placeholder = st.empty()
        table_placeholder.table(df)

        if st.button("Download All Transcripts"):
            videos_data = st.session_state['videos_data']
            folder_name = st.session_state['folder_name']
            progress_bar = st.progress(0)

            for i, video in enumerate(video_list):
                try:
                    video_url = videos_data[i][0]
                    transcript = fetch_transcript(video_url)
                    if transcript:
                        filename = get_video_title(video_url)
                        save_path = save_transcript_to_text(transcript, filename, folder_name)
                        if save_path:
                            video['Downloaded'] = '✅'
                        else:
                            video['Downloaded'] = '❌'
                    else:
                        video['Downloaded'] = '❌'

                    df = pd.DataFrame(video_list)
                    table_placeholder.table(df)
                    progress_bar.progress((i + 1) / len(video_list))

                except Exception as e:
                    logger.error(f"Error downloading transcript for video {video['Video Title']}: {str(e)}")
                    video['Downloaded'] = '❌'
                    continue

            successful = sum(1 for v in video_list if v['Downloaded'] == '✅')
            st.success(f"Successfully downloaded {successful} out of {len(video_list)} transcripts to {folder_name}")
            logger.info(f"All available video transcripts downloaded to {folder_name}")