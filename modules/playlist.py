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
from selenium.common.exceptions import TimeoutException, WebDriverException
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
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')

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


def get_playlist_info_selenium(playlist_url):
    """Get playlist information using Selenium with improved selectors."""
    driver = None
    try:
        driver = setup_chrome_driver()
        driver.set_page_load_timeout(30)
        wait = WebDriverWait(driver, 20)

        logger.info(f"Loading playlist URL: {playlist_url}")
        driver.get(playlist_url)
        time.sleep(5)  # Initial wait for JavaScript to load

        # Get playlist title with multiple selectors
        title_selectors = [
            "h1.style-scope.ytd-playlist-header-renderer",
            "yt-formatted-string.style-scope.ytd-playlist-sidebar-primary-info-renderer",
            "h1.ytd-playlist-header-renderer",
            "h1"
        ]

        playlist_title = None
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

        logger.info(f"Found playlist title: {playlist_title}")

        # Scroll to load all videos
        scroll_pause_time = 2
        scroll_timeout = 120  # 2 minutes timeout
        scroll_start_time = datetime.now()

        # Try to get total video count
        try:
            count_selectors = [
                "span.style-scope.ytd-playlist-sidebar-primary-info-renderer",
                "#stats.ytd-playlist-sidebar-primary-info-renderer yt-formatted-string"
            ]
            total_videos = None
            for selector in count_selectors:
                try:
                    count_element = driver.find_element(By.CSS_SELECTOR, selector)
                    count_text = count_element.text
                    if count_text:
                        total_videos = int(''.join(filter(str.isdigit, count_text)))
                        break
                except:
                    continue

            if total_videos:
                logger.info(f"Expected number of videos: {total_videos}")
        except:
            total_videos = None
            logger.warning("Could not determine total number of videos")

        # Scroll until we find all videos or timeout
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        found_videos = []

        while True:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(scroll_pause_time)

            # Update found videos
            try:
                selectors = [
                    "ytd-playlist-video-renderer",  # New playlist interface
                    "ytd-playlist-panel-video-renderer",  # Embedded playlist
                    "ytd-compact-video-renderer",  # Alternative view
                    "a#video-title"  # Direct video links
                ]

                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"Found {len(elements)} videos with selector '{selector}'")
                        for element in elements:
                            try:
                                # Try different methods to get video URL and title
                                link = None
                                title = None

                                # Get URL
                                try:
                                    link = element.get_attribute("href")
                                except:
                                    try:
                                        link = element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                                    except:
                                        try:
                                            link = element.find_element(By.CSS_SELECTOR, "a#video-title").get_attribute(
                                                "href")
                                        except:
                                            continue

                                # Get title
                                try:
                                    title = element.get_attribute("title")
                                except:
                                    try:
                                        title = element.text
                                    except:
                                        try:
                                            title = element.find_element(By.CSS_SELECTOR, "[title]").get_attribute(
                                                "title")
                                        except:
                                            title = f"Video_{len(found_videos) + 1}"

                                if link and title and 'watch?v=' in link:
                                    video_data = {
                                        'url': link,
                                        'title': sanitize_filename(title)
                                    }
                                    if video_data not in found_videos:
                                        found_videos.append(video_data)
                                        logger.info(f"Added video: {title}")
                            except Exception as e:
                                logger.error(f"Error processing video element: {str(e)}")
                                continue

                        if found_videos:
                            break  # Found videos with this selector, stop trying others

            except Exception as e:
                logger.error(f"Error finding videos: {str(e)}")

            # Check completion conditions
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                logger.info("Reached end of playlist")
                break

            if total_videos and len(found_videos) >= total_videos:
                logger.info("Found all expected videos")
                break

            if (datetime.now() - scroll_start_time).total_seconds() > scroll_timeout:
                logger.warning("Scroll timeout reached")
                break

            last_height = new_height
            logger.info(f"Found {len(found_videos)} videos so far...")

        if driver:
            driver.quit()

        if not found_videos:
            logger.error("No videos found in playlist")
            return None, None

        # Remove duplicates based on URL
        unique_videos = list({v['url']: v for v in found_videos}.values())
        logger.info(f"Final count: {len(unique_videos)} unique videos")

        return sanitize_filename(playlist_title), unique_videos

    except Exception as e:
        error_msg = f"Error fetching playlist info: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
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
                logger.info(f"Successfully saved transcript for: {video_data['title']}")
                return True, f"Success: {video_data['title']}"
            else:
                logger.error(f"Failed to save transcript file for: {video_data['title']}")
                return False, f"Failed to save transcript: {video_data['title']}"
        else:
            logger.warning(f"No transcript available for: {video_data['title']}")
            return False, f"No transcript available: {video_data['title']}"
    except Exception as e:
        error_msg = f"Error processing {video_data['title']}: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return False, error_msg


def render(config):
    """Render the playlist tab."""
    st.header("Playlist Transcripts")
    playlist_url = st.text_input("Enter YouTube Playlist URL:")

    if st.button("Download Playlist Transcripts"):
        if not playlist_url:
            st.warning("Please enter a valid YouTube Playlist URL.")
            return

        try:
            with st.spinner("Fetching playlist information..."):
                logger.info(f"Starting playlist download process for URL: {playlist_url}")
                status_placeholder = st.empty()
                status_placeholder.info("Loading playlist data... This may take a few moments.")

                playlist_title, videos_data = get_playlist_info_selenium(playlist_url)

                if not playlist_title or not videos_data:
                    error_msg = "Failed to fetch playlist information. Please check the URL and try again."
                    logger.error(error_msg)
                    st.error(error_msg)
                    return

                status_placeholder.success(f"Found {len(videos_data)} videos in playlist")

                folder_name = os.path.join(config['download_folder'], playlist_title)
                create_folder(folder_name)

                status_data = []
                progress_bar = st.progress(0)
                status_table = st.empty()

                for i, video_data in enumerate(videos_data):
                    try:
                        success, message = process_playlist_video(video_data, folder_name)

                        status_data.append({
                            'Title': video_data['title'],
                            'Status': '✅' if success else '❌',
                            'Message': message
                        })

                        progress_bar.progress((i + 1) / len(videos_data))
                        df = pd.DataFrame(status_data)
                        status_table.dataframe(df)

                    except Exception as e:
                        logger.error(f"Error processing video {video_data['title']}: {str(e)}")
                        status_data.append({
                            'Title': video_data['title'],
                            'Status': '❌',
                            'Message': f"Error: {str(e)}"
                        })
                        continue

                successful = sum(1 for s in status_data if s['Status'] == '✅')
                st.success(
                    f"Processed {len(videos_data)} videos. Successfully downloaded {successful} transcripts to {folder_name}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Download Summary Report"):
                        df = pd.DataFrame(status_data)
                        report_path = os.path.join(folder_name, f"{playlist_title}_report.csv")
                        df.to_csv(report_path, index=False)
                        st.success(f"Summary report saved to {report_path}")

                with col2:
                    if st.button("View Current Logs"):
                        st.text_area("Recent Logs", get_session_logs(), height=200)

        except Exception as e:
            error_msg = f"Error processing playlist: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            st.error(f"Error processing playlist: {str(e)}")