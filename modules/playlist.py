import streamlit as st
import pandas as pd
from datetime import datetime
import traceback
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url
)
from utils.table_utils import render_with_progress
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from modules.single_video import render_url as default_single_video_processor


def get_playlist_title(playlist_url, driver):
    """Extract playlist title using Selenium"""
    try:
        driver.get(playlist_url)
        # Wait for the title element to be present
        time.sleep(3) # Allow time for dynamic content to load
        title_element = driver.find_element(By.CSS_SELECTOR, "yt-formatted-string.style-scope.ytd-playlist-header-renderer")
        playlist_title = title_element.text
        if not playlist_title: # Fallback if specific selector fails
            playlist_title = driver.title.replace("- YouTube", "").strip()
        return sanitize_filename(playlist_title)
    except Exception as e:
        logger.error(f"Error extracting playlist title with Selenium: {e}")
        logger.error(traceback.format_exc())
        return f"Playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def fetch_playlist_videos(playlist_url, driver):
    """Fetch videos from playlist using Selenium"""
    videos = []
    try:
        driver.get(playlist_url)
        time.sleep(5)  # Wait for initial page load

        # Scroll to load all videos
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)  # Wait for new videos to load
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Extract video details
        video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        if not video_elements: # Fallback selector
            video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-panel-video-renderer")

        for video_element in video_elements:
            try:
                title_element = video_element.find_element(By.ID, "video-title")
                link_element = video_element.find_element(By.ID, "video-title") # Title element is usually the link too
                
                title = title_element.get_attribute("title") or title_element.text
                url = link_element.get_attribute("href")
                
                if title and url:
                    video_id = get_video_id_from_url(url)
                    if video_id: # Ensure it's a valid video URL
                        videos.append({
                            "id": video_id,
                            "title": sanitize_filename(title),
                            "url": url,
                            "type": "video" # Assuming all are videos
                        })
            except Exception as e:
                logger.warning(f"Could not extract details for a video in playlist: {e}")
        
        if not videos:
            st.warning("No videos found in the playlist using Selenium, or failed to extract details.")
            logger.warning(f"No videos extracted from playlist URL: {playlist_url}")
        return videos

    except Exception as e:
        st.error(f"Error fetching playlist videos with Selenium: {e}")
        logger.error(f"Error fetching playlist videos with Selenium for URL {playlist_url}: {e}")
        logger.error(traceback.format_exc())
        return None


def render_url(playlist_url: str, config: dict):
    """Process a playlist URL using Selenium"""
    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        edge_options = EdgeOptions()
        # Remove headless mode to see what's happening
        # edge_options.add_argument("--headless")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36 Edg/90.0.818.66")
        
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=edge_options)
    except Exception as e:
        logger.warning(f"Failed to setup Edge driver: {str(e)}, falling back to Chrome")
        # Fallback to Chrome
        chrome_options = ChromeOptions()
        # Remove headless mode to see what's happening
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        playlist_title_text = get_playlist_title(playlist_url, driver)
        config['name_extractor'] = lambda url: playlist_title_text # Use the extracted title

        # The fetch_playlist_videos now needs the driver
        # We need to adapt render_with_progress or how it calls fetch_playlist_videos
        # For now, let's call fetch_playlist_videos directly and then pass its result
        # to a modified rendering logic if render_with_progress is too complex to change now.

        st.info(f"Extracting videos from playlist: {playlist_title_text}")
        video_items = fetch_playlist_videos(playlist_url, driver)

        if video_items:
            # Create a temporary folder for this playlist
            playlist_folder_name = sanitize_filename(playlist_title_text)
            base_path = config.get("base_path", "transcriptions")
            
            # Ensure the main transcriptions folder exists and has correct permissions
            if not os.path.exists(base_path):
                create_folder(base_path) # create_folder should handle permissions if possible
            
            # Path for the current playlist's transcriptions
            playlist_output_path = os.path.join(base_path, playlist_folder_name)
            create_folder(playlist_output_path)
            config["output_path"] = playlist_output_path # Set output path for individual videos

            st.success(f"Created folder for playlist: {playlist_output_path}")
            logger.info(f"Output path for playlist '{playlist_title_text}': {playlist_output_path}")

            # Update config for render_with_progress to use the pre-fetched items
            # render_with_progress expects a function that takes a URL, not pre-fetched items.
            # This part needs careful refactoring of render_with_progress or a new approach.
            # For a direct fix, we can iterate here and call the transcription for each video.
            
            # Simplified processing loop (bypassing render_with_progress for this direct implementation)
            total_videos = len(video_items)
            st.write(f"Found {total_videos} videos in the playlist.")
            
            # Get the actual video transcription function from config
            # This assumes config['api_handler'] is the function like process_video_url
            if 'api_handler' not in config or not config.get('api_handler'):
                logger.info("api_handler not found or not set in config. Using default_single_video_processor from module import.")
                config['api_handler'] = default_single_video_processor # Relies on the module-level import

            video_processor_func = config.get('api_handler')
            if not video_processor_func:
                # This case should ideally not be hit if default_single_video_processor is a valid function.
                st.error("Video processing function (api_handler) is missing or invalid in config even after attempting to set default.")
                logger.error("api_handler is None or missing after attempting to set default from default_single_video_processor.")
                return

            all_transcripts_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, video_info in enumerate(video_items):
                status_text.text(f"Processing video {i+1}/{total_videos}: {video_info['title']}")
                logger.info(f"Processing video from playlist: {video_info['title']} ({video_info['url']})")
                try:
                    # Each video is processed individually using the existing mechanism
                    # The process_video_url (or equivalent) should handle individual video transcription
                    # and saving. It needs the video_info (id, title, url) and config.
                    
                    # We need to ensure the 'name_extractor' for individual videos uses the video title
                    current_video_config = config.copy()
                    current_video_config['name_extractor'] = lambda u: video_info['title']
                    current_video_config['output_filename_prefix'] = video_info['title'] # For saving

                    # The video_processor_func (e.g. modules.single_video.process_video_url)
                    # typically takes a URL and config.
                    # It returns transcript_data, filename, error
                    transcript_data, output_filename, error_message = video_processor_func(video_info['url'], current_video_config)
                    
                    if transcript_data:
                        all_transcripts_data.append({
                            "Video Title": video_info['title'],
                            "URL Fetched": "✅",
                            "Video Downloaded": "✅",
                            "Transcript": transcript_data,
                            "Filename": output_filename,
                            "Status": "Success"
                        })
                        logger.info(f"Successfully transcribed: {video_info['title']}")
                    else:
                        all_transcripts_data.append({
                            "Video Title": video_info['title'],
                            "URL Fetched": "✅",
                            "Video Downloaded": "❌",
                            "Transcript": "N/A",
                            "Filename": "N/A",
                            "Status": f"Failed: {error_message or 'Unknown error'}"
                        })
                        logger.error(f"Failed to transcribe: {video_info['title']}. Error: {error_message}")

                except Exception as e:
                    logger.error(f"Error processing video '{video_info['title']}' from playlist: {e}")
                    logger.error(traceback.format_exc())
                    all_transcripts_data.append({
                        "Video Title": video_info['title'],
                        "URL Fetched": "✅",
                        "Video Downloaded": "❌",
                        "Transcript": "N/A",
                        "Filename": "N/A",
                        "Status": f"Failed: {str(e)}"
                    })
                progress_bar.progress((i + 1) / total_videos)
            
            status_text.text("Playlist processing complete.")
            st.success("All videos in the playlist processed.")

            if all_transcripts_data:
                df = pd.DataFrame(all_transcripts_data)
                st.dataframe(df)
            else:
                st.warning("No transcripts were generated from the playlist.")

        elif video_items is None: # fetch_playlist_videos returned None due to error
             st.error("Could not retrieve video list from playlist due to an error.")
        else: # video_items is an empty list
             st.info("No videos found in the specified playlist.")
             
    except Exception as e:
        st.error(f"An unexpected error occurred during playlist processing: {e}")
        logger.error(f"Unexpected error in render_url for playlist: {e}")
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
    
    # Original render_with_progress call is being replaced by the loop above.
    # If render_with_progress is essential, it needs to be refactored to accept a list of items
    # or the fetch_playlist_videos needs to be passed as a callable that render_with_progress can use.
    # For now, this direct loop provides the functionality.
    return # render_with_progress(
        # fetch_playlist_videos, # This would need to be a function that takes (playlist_url, config)
                                 # and uses the driver internally, or driver is passed somehow.
        # playlist_url,
        # config,
        # item_type='video'
    # )


def render(config):
    """Render method for playlist"""
    """Process a playlist URL - maintained for backward compatibility"""
    config['name_extractor'] = get_playlist_title
    return render_with_progress(
        fetch_playlist_videos,
        playlist_url,
        config,
        item_type='video'
    )


def render(config):
    """Render method for playlist"""
    st.header("Playlist Transcripts")
    playlist_url = st.text_input("Enter YouTube Playlist URL:")

    if st.button("Download Playlist Transcripts"):
        if playlist_url:
            with st.spinner("Downloading playlist transcripts..."):
                render_url(playlist_url, config)
        else:
            st.warning("Please enter a valid YouTube Playlist URL.")
