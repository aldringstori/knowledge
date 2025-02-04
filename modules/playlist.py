import streamlit as st
import pandas as pd
from datetime import datetime
import traceback
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    fetch_transcript,
    save_transcript_to_text,
    get_video_id_from_url
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
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
        options.add_argument('--disable-notifications')

        service = ChromeService(log_output=os.path.devnull)
        return webdriver.Chrome(options=options, service=service)
    except Exception as e:
        logger.error(f"Chrome WebDriver setup failed: {str(e)}")
        raise


def get_playlist_info(playlist_url):
    """Get playlist information using Selenium."""
    driver = None
    try:
        driver = setup_chrome_driver()
        wait = WebDriverWait(driver, 20)
        logger.info(f"Loading playlist URL: {playlist_url}")

        driver.get(playlist_url)
        time.sleep(5)

        # Get playlist title
        playlist_title = None
        title_selectors = [
            "h1.style-scope.ytd-playlist-header-renderer",
            "yt-formatted-string.style-scope.ytd-playlist-sidebar-primary-info-renderer",
            "h1.ytd-playlist-header-renderer",
            "h1"
        ]

        for selector in title_selectors:
            try:
                title_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if title_element.text.strip():
                    playlist_title = title_element.text.strip()
                    break
            except:
                continue

        if not playlist_title:
            playlist_title = f"Playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Scroll to load all videos
        scroll_pause_time = 2
        scroll_timeout = 120
        scroll_start_time = time.time()
        found_videos = []
        last_height = driver.execute_script("return document.documentElement.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(scroll_pause_time)

            # Find videos
            selectors = [
                "ytd-playlist-video-renderer",
                "ytd-playlist-panel-video-renderer",
                "a#video-title"
            ]

            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        try:
                            # Get URL and title
                            url = element.get_attribute("href")
                            if not url:
                                url = element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")

                            title = element.get_attribute("title")
                            if not title:
                                title = element.text or f"Video_{len(found_videos) + 1}"

                            if url and title and 'watch?v=' in url:
                                video_data = {
                                    'url': url,
                                    'title': sanitize_filename(title)
                                }
                                if video_data not in found_videos:
                                    found_videos.append(video_data)
                        except Exception as e:
                            logger.error(f"Error processing video element: {str(e)}")
                            continue

            # Check if scrolling should stop
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height or time.time() - scroll_start_time > scroll_timeout:
                break
            last_height = new_height

        if driver:
            driver.quit()

        if not found_videos:
            return None, None

        # Remove duplicates
        unique_videos = list({v['url']: v for v in found_videos}.values())
        return sanitize_filename(playlist_title), unique_videos

    except Exception as e:
        logger.error(f"Error fetching playlist info: {str(e)}")
        if driver:
            driver.quit()
        return None, None


def process_playlist_video(video_data, folder_name):
    """Process a single video from the playlist."""
    try:
        logger.info(f"Processing video: {video_data['title']}")
        transcript = fetch_transcript(video_data['url'])

        if transcript:
            save_path = save_transcript_to_text(
                transcript,
                video_data['title'],
                folder_name
            )
            if save_path:
                return True, f"Success: {video_data['title']}"
            return False, f"Failed to save transcript: {video_data['title']}"
        return False, f"No transcript available: {video_data['title']}"

    except Exception as e:
        error_msg = f"Error processing {video_data['title']}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def render_url(playlist_url: str, config: dict):
    """Process a playlist URL"""
    try:
        logger.info(f"Processing playlist URL: {playlist_url}")
        status_placeholder = st.empty()
        status_placeholder.info("Loading playlist data... This may take a few moments.")

        playlist_title, videos_data = get_playlist_info(playlist_url)
        if not playlist_title or not videos_data:
            st.error("Failed to fetch playlist information")
            return False

        status_placeholder.success(f"Found {len(videos_data)} videos in playlist")
        folder_name = os.path.join(config['download_folder'], playlist_title)
        create_folder(folder_name)

        status_data = []
        progress_bar = st.progress(0)
        status_table = st.empty()

        for i, video_data in enumerate(videos_data):
            success, message = process_playlist_video(video_data, folder_name)
            status_data.append({
                'Title': video_data['title'],
                'Status': '✅' if success else '❌',
                'Message': message
            })

            progress_bar.progress((i + 1) / len(videos_data))
            status_table.dataframe(pd.DataFrame(status_data))

        successful = sum(1 for s in status_data if s['Status'] == '✅')
        st.success(f"Downloaded {successful} out of {len(videos_data)} transcripts to {folder_name}")

        # Export report option
        if st.button("Download Summary Report"):
            df = pd.DataFrame(status_data)
            report_path = os.path.join(folder_name, f"{playlist_title}_report.csv")
            df.to_csv(report_path, index=False)
            st.success(f"Summary report saved to {report_path}")

        return True

    except Exception as e:
        logger.error(f"Error processing playlist: {str(e)}")
        st.error(f"Error processing playlist: {str(e)}")
        return False


def render(config):
    """Legacy render method for backward compatibility"""
    st.header("Playlist Transcripts")
    playlist_url = st.text_input("Enter YouTube Playlist URL:")
    if st.button("Download Playlist Transcripts"):
        if playlist_url:
            with st.spinner("Downloading playlist transcripts..."):
                render_url(playlist_url, config)
        else:
            st.warning("Please enter a valid YouTube Playlist URL.")