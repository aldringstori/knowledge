import streamlit as st
import pandas as pd
from datetime import datetime
import traceback
import time
from utils.logging_setup import get_playlist_logger
from utils.channel_manager import ChannelManager

# Get module-specific logger
logger = get_playlist_logger()
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url
)
from utils.table_utils import render_with_progress
from utils.playlist_cache import PlaylistCache
import time
import os
import zipfile
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from modules.single_video import render_url as default_single_video_processor


def create_transcriptions_zip(output_path, playlist_title):
    """Create a ZIP file containing all transcription files from the output directory"""
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Get all text files in the directory and subdirectories
            file_count = 0
            for root, dirs, files in os.walk(output_path):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        # Create archive name relative to output_path
                        arcname = os.path.relpath(file_path, output_path)
                        zip_file.write(file_path, arcname)
                        file_count += 1
            
            # Add a summary file
            summary_content = f"""Playlist: {playlist_title}
Total transcription files: {file_count}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Files included:
"""
            for root, dirs, files in os.walk(output_path):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, output_path)
                        # Get file size
                        file_size = os.path.getsize(file_path)
                        summary_content += f"- {arcname} ({file_size} bytes)\n"
            
            zip_file.writestr("_playlist_summary.txt", summary_content)
            
        zip_buffer.seek(0)
        return zip_buffer.getvalue(), file_count
        
    except Exception as e:
        logger.error(f"Error creating ZIP file: {e}")
        return None, 0


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


def fetch_playlist_videos(playlist_url, driver, config=None):
    """Fetch videos from playlist using Selenium with configurable selectors"""
    from utils.config import get_config
    
    if config is None:
        config = get_config()
    
    videos = []
    try:
        driver.get(playlist_url)
        time.sleep(5)  # Wait for initial page load

        # Scroll to load all videos
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        while scroll_attempts < max_scroll_attempts:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(3)  # Wait for new videos to load
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_attempts += 1

        # Get selectors from config
        primary_selector = config.get('youtube_playlist_video_renderer_class', 'ytd-playlist-video-renderer')
        fallback_selector = config.get('youtube_playlist_fallback_container_class', 'ytd-playlist-panel-video-renderer')
        title_id = config.get('youtube_playlist_video_title_id', 'video-title')
        
        logger.info(f"Using primary selector: {primary_selector}")
        logger.info(f"Using fallback selector: {fallback_selector}")
        
        # Extract video details with multiple selector attempts
        video_elements = driver.find_elements(By.CSS_SELECTOR, primary_selector)
        if not video_elements:
            logger.warning(f"No videos found with primary selector {primary_selector}, trying fallback")
            video_elements = driver.find_elements(By.CSS_SELECTOR, fallback_selector)
            
        if not video_elements:
            logger.warning("No video elements found with any selector, trying alternative approaches")
            # Additional fallback selectors
            alternative_selectors = [
                "ytd-playlist-video-renderer",
                "ytd-playlist-panel-video-renderer",
                "[id*='video-title']",
                "a[href*='/watch']"
            ]
            for alt_selector in alternative_selectors:
                video_elements = driver.find_elements(By.CSS_SELECTOR, alt_selector)
                if video_elements:
                    logger.info(f"Found {len(video_elements)} elements with alternative selector: {alt_selector}")
                    break

        logger.info(f"Found {len(video_elements)} video elements to process")
        
        for i, video_element in enumerate(video_elements):
            try:
                # Try multiple approaches to find title and URL
                title_element = None
                link_element = None
                
                # Approach 1: Use configured ID
                try:
                    title_element = video_element.find_element(By.ID, title_id)
                    link_element = title_element  # Title element is usually the link too
                except:
                    pass
                
                # Approach 2: Try alternative selectors if first approach fails
                if not title_element:
                    alternative_title_selectors = [
                        "a[id='video-title']",
                        "a[href*='/watch']",
                        "#video-title",
                        ".ytd-playlist-video-renderer a",
                        "h3 a"
                    ]
                    
                    for selector in alternative_title_selectors:
                        try:
                            title_element = video_element.find_element(By.CSS_SELECTOR, selector)
                            link_element = title_element
                            logger.debug(f"Found title element with selector: {selector}")
                            break
                        except:
                            continue
                
                if title_element and link_element:
                    title = title_element.get_attribute("title") or title_element.text or title_element.get_attribute("aria-label")
                    url = link_element.get_attribute("href")
                    
                    # Clean up URL (remove playlist parameters for individual video processing)
                    if url and "&list=" in url:
                        url = url.split("&list=")[0]
                    
                    if title and url and "/watch?v=" in url:
                        video_id = get_video_id_from_url(url)
                        if video_id:
                            clean_title = sanitize_filename(title.strip())
                            if clean_title:  # Only add if title is not empty
                                videos.append({
                                    "id": video_id,
                                    "title": clean_title,
                                    "url": url,
                                    "type": "video"
                                })
                                logger.debug(f"Added video {len(videos)}: {clean_title[:50]}...")
                            else:
                                logger.warning(f"Empty title for video {i+1}, skipping")
                        else:
                            logger.warning(f"Could not extract video ID from URL: {url}")
                    else:
                        logger.warning(f"Invalid title or URL for video {i+1}: title='{title}', url='{url}'")
                else:
                    logger.warning(f"Could not find title/link elements for video {i+1}")
                    
            except Exception as e:
                logger.warning(f"Could not extract details for video {i+1}: {e}")
                logger.debug(f"Video element HTML snippet: {video_element.get_attribute('outerHTML')[:200]}...")
        
        if not videos:
            st.warning("No videos found in the playlist using Selenium, or failed to extract details.")
            logger.warning(f"No videos extracted from playlist URL: {playlist_url}")
            logger.warning(f"Tried selectors: {primary_selector}, {fallback_selector}")
            
            # Debug information
            page_source_snippet = driver.page_source[:1000] if driver.page_source else "No page source"
            logger.debug(f"Page source snippet: {page_source_snippet}")
        else:
            logger.info(f"Successfully extracted {len(videos)} videos from playlist")
            
        return videos

    except Exception as e:
        st.error(f"Error fetching playlist videos with Selenium: {e}")
        logger.error(f"Error fetching playlist videos with Selenium for URL {playlist_url}: {e}")
        logger.error(traceback.format_exc())
        return None


def retry_failed_videos():
    """Retry downloading failed videos from the last playlist processing"""
    if 'playlist_failed_videos' not in st.session_state or not st.session_state.playlist_failed_videos:
        st.warning("No failed videos to retry.")
        return
        
    failed_videos = st.session_state.playlist_failed_videos
    config = st.session_state.playlist_config
    progress_data = st.session_state.playlist_progress_data.copy()
    videos_to_process = st.session_state.playlist_videos_to_process
    playlist_output_path = st.session_state.playlist_output_path
    
    st.header("🔄 Retrying Failed Downloads")
    st.info(f"Retrying {len(failed_videos)} failed videos...")
    
    # Display initial table with only failed videos FIRST
    retry_table_placeholder = st.empty()
    retry_df = pd.DataFrame([progress_data[fv['progress_index']] for fv in failed_videos])
    with retry_table_placeholder.container():
        st.dataframe(retry_df, use_container_width=True, hide_index=True)
    
    # Create progress tracking below table
    retry_progress_bar = st.progress(0)
    retry_status_text = st.empty()
    
    successful_retries = 0
    failed_retries = 0
    
    for i, failed_video in enumerate(failed_videos):
        video_info = failed_video['video_info']
        original_index = failed_video['progress_index']
        start_time = time.time()
        
        retry_status_text.text(f"🔄 Retrying video {i+1}/{len(failed_videos)}: {video_info['title'][:60]}...")
        
        # Update progress data for this video
        progress_data[original_index]["Status"] = "Retrying..."
        progress_data[original_index]["Transcript Downloaded"] = "🔄"
        
        # Update display
        retry_df = pd.DataFrame([progress_data[fv['progress_index']] for fv in failed_videos])
        with retry_table_placeholder.container():
            st.dataframe(retry_df, use_container_width=True, hide_index=True)
        
        logger.info(f"Retrying video {i+1}/{len(failed_videos)}: {video_info['title']} ({video_info['url']})")
        
        try:
            # Check if transcript now exists (maybe fixed in the meantime)
            expected_filename = os.path.join(playlist_output_path, f"{sanitize_filename(video_info['title'])}.txt")
            
            if os.path.exists(expected_filename):
                # File now exists, mark as success
                processing_time = time.time() - start_time
                progress_data[original_index]["Transcript Downloaded"] = "✅"
                progress_data[original_index]["Status"] = "Success (retry)"
                progress_data[original_index]["File"] = os.path.basename(expected_filename)
                progress_data[original_index]["Duration"] = f"{processing_time:.1f}s"
                successful_retries += 1
                logger.info(f"✅ Retry successful (file exists): {video_info['title']}")
            else:
                # Retry processing
                current_video_config = config.copy()
                current_video_config['output_filename_prefix'] = video_info['title']
                
                # Use single video processor for retry
                transcript_data, output_filename, error_message = default_single_video_processor(
                    video_info['url'], 
                    current_video_config
                )
                
                processing_time = time.time() - start_time
                
                if transcript_data and output_filename:
                    # Retry successful
                    progress_data[original_index]["Transcript Downloaded"] = "✅"
                    progress_data[original_index]["Status"] = "Success (retry)"
                    progress_data[original_index]["File"] = os.path.basename(output_filename)
                    successful_retries += 1
                    logger.info(f"✅ Retry successful: {video_info['title']}")
                else:
                    # Retry failed
                    progress_data[original_index]["Transcript Downloaded"] = "❌"
                    progress_data[original_index]["Status"] = f"Failed (retry): {error_message or 'Unknown error'}"
                    failed_retries += 1
                    logger.error(f"❌ Retry failed: {video_info['title']}. Error: {error_message}")
                
                progress_data[original_index]["Duration"] = f"{processing_time:.1f}s"
            
        except Exception as e:
            processing_time = time.time() - start_time
            progress_data[original_index]["Transcript Downloaded"] = "❌"
            progress_data[original_index]["Status"] = f"Error (retry): {str(e)[:50]}"
            progress_data[original_index]["Duration"] = f"{processing_time:.1f}s"
            failed_retries += 1
            logger.error(f"❌ Error during retry for video '{video_info['title']}': {e}")
        
        # Update progress bar
        retry_progress_bar.progress((i + 1) / len(failed_videos))
        
        # Update display
        retry_df = pd.DataFrame([progress_data[fv['progress_index']] for fv in failed_videos])
        with retry_table_placeholder.container():
            st.dataframe(retry_df, use_container_width=True, hide_index=True)
        
        # Add delay between retries
        if i < len(failed_videos) - 1:
            download_delay = config.get('download_delay_seconds', 3)
            retry_status_text.text(f"⏱️ Waiting {download_delay}s before next retry...")
            time.sleep(download_delay)
    
    # Final retry status
    retry_status_text.text("✅ Retry process complete!")
    
    # Update session state with new results
    st.session_state.playlist_progress_data = progress_data
    
    # Update failed videos list (remove successful retries)
    remaining_failed = []
    for failed_video in failed_videos:
        original_index = failed_video['progress_index']
        if progress_data[original_index]["Status"].startswith("Failed") or progress_data[original_index]["Status"].startswith("Error"):
            remaining_failed.append(failed_video)
    
    st.session_state.playlist_failed_videos = remaining_failed
    
    # Summary
    st.success(f"🎉 Retry completed!")
    st.write(f"**Retry Summary:**")
    st.write(f"- ✅ Successful retries: {successful_retries}")
    st.write(f"- ❌ Failed retries: {failed_retries}")
    st.write(f"- 📁 Output folder: {playlist_output_path}")
    
    if remaining_failed:
        st.warning(f"⚠️ {len(remaining_failed)} videos still failed after retry.")
    else:
        st.success("🎉 All failed videos have been successfully processed!")
        # Clear failed videos from session state
        if 'playlist_failed_videos' in st.session_state:
            del st.session_state.playlist_failed_videos
    
    # Save updated results
    results_file = os.path.join(playlist_output_path, "download_results.csv")
    df = pd.DataFrame(progress_data)
    df.to_csv(results_file, index=False)
    st.info(f"📊 Updated results saved to: {results_file}")


def render_url(playlist_url: str, config: dict):
    """Process a playlist URL using Selenium"""
    # Import the common driver setup function
    from utils.common import setup_selenium_driver
    
    # Get headless mode from config
    headless_mode = config.get('headless_mode', False)
    
    # Setup driver with configuration from environment
    driver = setup_selenium_driver(
        headless=headless_mode,
        use_gpu=config.get('selenium_use_gpu', True),
        window_size=config.get('selenium_window_size', '1920,1080'),
        user_agent=config.get('selenium_user_agent')
    )
    if driver is None:
        st.warning("⚠️ Selenium WebDriver not available - Playlist processing requires browser automation")
        st.info("💡 **To enable full playlist processing:**")
        
        with st.expander("🔧 Setup Instructions"):
            st.write("**Option 1: Add Selenium service to docker-compose.yml**")
            st.code("""
# Add to your docker-compose.yml:
services:
  knowledge-app:
    # ... existing config ...
    environment:
      - SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
    depends_on:
      - selenium
    networks:
      - knowledge-net

  selenium:
    image: selenium/standalone-chrome:latest
    ports:
      - "4444:4444"
    environment:
      - SE_NODE_MAX_SESSIONS=2
    volumes:
      - /dev/shm:/dev/shm
    networks:
      - knowledge-net

networks:
  knowledge-net:
    driver: bridge
            """, language="yaml")
            
            st.write("**Option 2: Install Chrome in the main container**")
            st.code("""
# Add to Dockerfile before installing Python dependencies:
RUN apt-get update && apt-get install -y \\
    wget gnupg ca-certificates \\
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \\
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \\
    && apt-get update \\
    && apt-get install -y google-chrome-stable
            """, language="dockerfile")
        
        st.divider()
        st.info("📝 **Alternative: Process individual videos**")
        st.write("For now, you can extract individual video URLs from the playlist manually and process them one by one using the **Single Video** tab.")
        st.write("**Example:** `https://youtube.com/watch?v=VIDEO_ID`")
        
        logger.warning("Selenium WebDriver not available for playlist processing - user informed about setup options")
        return
    
    try:
        playlist_title_text = get_playlist_title(playlist_url, driver)
        config['name_extractor'] = lambda url: playlist_title_text # Use the extracted title

        # The fetch_playlist_videos now needs the driver
        # We need to adapt render_with_progress or how it calls fetch_playlist_videos
        # For now, let's call fetch_playlist_videos directly and then pass its result
        # to a modified rendering logic if render_with_progress is too complex to change now.

        # Get configuration for selectors
        from utils.config import get_config
        env_config = get_config()
        
        # Initialize playlist cache
        cache = PlaylistCache()
        
        # Phase 1: Check cache and extract video URLs
        st.info(f"📋 Phase 1: Checking cache and extracting video URLs from playlist: {playlist_title_text}")
        
        # Show current selector configuration
        with st.expander("🔧 Current Selector Configuration", expanded=False):
            st.code(f"""Primary Selector: {env_config.get('youtube_playlist_video_renderer_class')}
Fallback Selector: {env_config.get('youtube_playlist_fallback_container_class')}
Title ID: {env_config.get('youtube_playlist_video_title_id')}""", language="text")
        
        # Load cached data
        cached_data = cache.load_cached_playlist(playlist_url)
        if cached_data:
            st.info(f"🗄️ Found cached playlist data from {cached_data.get('last_fetched', 'unknown time')}")
            st.info(f"📊 Cached playlist contains {cached_data.get('total_videos', 0)} videos")
        
        # Fetch current playlist videos
        st.info("🔍 Fetching current playlist state...")
        video_items = fetch_playlist_videos(playlist_url, driver, env_config)

        if video_items:
            total_videos = len(video_items)
            st.success(f"✅ Found {total_videos} videos in the playlist")
            
            # Detect changes using cache
            new_videos, existing_videos, removed_videos = cache.detect_changes(playlist_url, video_items)
            
            # Show change detection results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🆕 New Videos", len(new_videos))
            with col2:
                st.metric("📁 Existing Videos", len(existing_videos))
            with col3:
                st.metric("🗑️ Removed Videos", len(removed_videos))
            
            if new_videos:
                st.info(f"🔥 Found {len(new_videos)} new videos to process!")
            elif existing_videos and not new_videos:
                st.info(f"📋 No new videos found. All {len(existing_videos)} videos were previously fetched.")
            
            if removed_videos:
                st.warning(f"⚠️ {len(removed_videos)} videos were removed from the playlist since last fetch.")
            
            # Create folder for playlist
            playlist_folder_name = sanitize_filename(playlist_title_text)
            base_path = config.get("download_folder", "transcriptions")
            
            # Debug: log the base path being used
            logger.info(f"Using base path: {base_path}")
            logger.info(f"Current working directory: {os.getcwd()}")
            
            # Ensure we're using absolute path if not already
            if not os.path.isabs(base_path):
                base_path = os.path.abspath(base_path)
                logger.info(f"Converted to absolute path: {base_path}")
            
            if not os.path.exists(base_path):
                base_path = create_folder(base_path)
            
            playlist_output_path = os.path.join(base_path, playlist_folder_name)
            playlist_output_path = create_folder(playlist_output_path)
            config["output_path"] = playlist_output_path

            st.success(f"📁 Created folder: {playlist_output_path}")
            logger.info(f"Output path for playlist '{playlist_title_text}': {playlist_output_path}")

            # Save video URLs to file for backup/reference
            urls_file = os.path.join(playlist_output_path, "video_urls.txt")
            try:
                with open(urls_file, 'w', encoding='utf-8') as f:
                    f.write(f"Playlist: {playlist_title_text}\n")
                    f.write(f"Total Videos: {total_videos}\n")
                    f.write(f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("-" * 50 + "\n")
                    for i, video in enumerate(video_items):
                        f.write(f"{i+1}. {video['title']}\n")
                        f.write(f"   URL: {video['url']}\n\n")
                
                st.info(f"💾 Video URLs saved to: {urls_file}")
            except Exception as e:
                st.warning(f"⚠️ Could not save video URLs file: {e}")
                logger.warning(f"Failed to save video URLs file: {e}")

            # Filter videos to process (new videos + existing videos that haven't been downloaded)
            videos_to_process = cache.filter_unprocessed_videos(new_videos + existing_videos, playlist_output_path)
            
            # Update cache with latest playlist state
            cache.save_playlist_cache(playlist_url, playlist_title_text, video_items)
            
            # Phase 2: Process transcripts with smart processing
            st.header("📥 Phase 2: Downloading Transcripts")
            
            if videos_to_process:
                st.info(f"🎯 Processing {len(videos_to_process)} videos ({len(new_videos)} new, {len(videos_to_process) - len(new_videos)} existing unprocessed)")
            else:
                st.success("✅ All videos have already been processed! No new downloads needed.")
                return  # Exit early if nothing to process
            
            # Initialize progress tracking table FIRST
            progress_data = []
            for i, video in enumerate(videos_to_process):
                progress_data.append({
                    "#": i + 1,
                    "Title": video['title'][:50] + "..." if len(video['title']) > 50 else video['title'],
                    "URL Fetched": "✅",
                    "Transcript Downloaded": "⏳",
                    "Status": "Pending",
                    "Duration": "0s",
                    "File": ""
                })
            
            # Create and display table container FIRST
            table_placeholder = st.empty()
            df = pd.DataFrame(progress_data)
            with table_placeholder.container():
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Create summary metrics below the table
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_metric = st.metric("Total to Process", len(videos_to_process))
            with col2:
                success_metric = st.metric("Downloaded", "0")
            with col3:
                failed_metric = st.metric("Failed", "0") 
            with col4:
                remaining_metric = st.metric("Remaining", len(videos_to_process))
            
            # Progress bar and status
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Get download delay from config
            download_delay = config.get('download_delay_seconds', 3)
            
            # Show settings info
            st.info(f"⚙️ Settings: Download delay = {download_delay}s, Headless mode = {'On' if config.get('headless_mode', False) else 'Off'}")
            
            # Process each video
            successful_downloads = 0
            failed_downloads = 0
            
            for i, video_info in enumerate(videos_to_process):
                start_time = time.time()
                
                # Update status  
                status_text.text(f"🔄 Processing video {i+1}/{len(videos_to_process)}: {video_info['title'][:60]}...")
                progress_data[i]["Status"] = "Processing..."
                progress_data[i]["Transcript Downloaded"] = "🔄"
                
                # Update table
                df = pd.DataFrame(progress_data)
                with table_placeholder.container():
                    st.dataframe(df, use_container_width=True, hide_index=True)
                
                logger.info(f"Processing video {i+1}/{len(videos_to_process)}: {video_info['title']} ({video_info['url']})")
                
                try:
                    # Check if transcript already exists (resume functionality)
                    expected_filename = os.path.join(playlist_output_path, f"{sanitize_filename(video_info['title'])}.txt")
                    
                    if os.path.exists(expected_filename):
                        # File already exists, skip processing
                        processing_time = time.time() - start_time
                        progress_data[i]["Transcript Downloaded"] = "✅"
                        progress_data[i]["Status"] = "Already exists"
                        progress_data[i]["File"] = os.path.basename(expected_filename)
                        progress_data[i]["Duration"] = f"{processing_time:.1f}s"
                        successful_downloads += 1
                        logger.info(f"⏭️ Skipped (already exists): {video_info['title']}")
                    else:
                        # Process video with current config
                        current_video_config = config.copy()
                        current_video_config['output_filename_prefix'] = video_info['title']
                        
                        # Reuse single video logic for transcript download
                        transcript_data, output_filename, error_message = default_single_video_processor(
                            video_info['url'], 
                            current_video_config
                        )
                        
                        # Track video download in channel manager if successful
                        if transcript_data and output_filename:
                            try:
                                cm = ChannelManager()
                                if cm.track_video_download(video_info['url'], video_info['title'], output_filename):
                                    logger.info(f"Video tracked for channel management: {video_info['title']}")
                            except Exception as e:
                                logger.warning(f"Could not track video for channel management: {e}")
                        
                        # Calculate processing time
                        processing_time = time.time() - start_time
                        
                        if transcript_data and output_filename:
                            # Success
                            progress_data[i]["Transcript Downloaded"] = "✅"
                            progress_data[i]["Status"] = "Success"
                            progress_data[i]["File"] = os.path.basename(output_filename)
                            successful_downloads += 1
                            logger.info(f"✅ Successfully downloaded: {video_info['title']}")
                        else:
                            # Failed
                            progress_data[i]["Transcript Downloaded"] = "❌"
                            progress_data[i]["Status"] = f"Failed: {error_message or 'Unknown error'}"
                            failed_downloads += 1
                            logger.error(f"❌ Failed to download: {video_info['title']}. Error: {error_message}")
                        
                        progress_data[i]["Duration"] = f"{processing_time:.1f}s"
                    
                except Exception as e:
                    processing_time = time.time() - start_time
                    progress_data[i]["Transcript Downloaded"] = "❌"
                    progress_data[i]["Status"] = f"Error: {str(e)[:50]}"
                    progress_data[i]["Duration"] = f"{processing_time:.1f}s"
                    failed_downloads += 1
                    logger.error(f"❌ Error processing video '{video_info['title']}': {e}")
                
                # Update progress bar
                progress_bar.progress((i + 1) / len(videos_to_process))
                
                # Update table with current results
                df = pd.DataFrame(progress_data)
                with table_placeholder.container():
                    st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Update summary metrics
                remaining = len(videos_to_process) - (i + 1)
                with col2:
                    st.metric("Downloaded", successful_downloads)
                with col3:
                    st.metric("Failed", failed_downloads)
                with col4:
                    st.metric("Remaining", remaining)
                
                # Add delay between downloads (don't rush)
                if i < len(videos_to_process) - 1:  # Don't delay after the last video
                    status_text.text(f"⏱️ Waiting {download_delay}s before next download...")
                    time.sleep(download_delay)
            
            # Final status
            status_text.text("✅ Playlist processing complete!")
            
            # Summary
            st.success(f"🎉 Processing completed!")
            st.write(f"**Summary:**")
            st.write(f"- ✅ Successful downloads: {successful_downloads}")
            st.write(f"- ❌ Failed downloads: {failed_downloads}")
            st.write(f"- 📁 Output folder: {playlist_output_path}")
            
            # Save final results to CSV
            results_file = os.path.join(playlist_output_path, "download_results.csv")
            df.to_csv(results_file, index=False)
            st.info(f"📊 Results saved to: {results_file}")
            
            # Store failed videos in session state for retry functionality
            failed_videos = []
            for i, video in enumerate(videos_to_process):
                if progress_data[i]["Status"].startswith("Failed") or progress_data[i]["Status"].startswith("Error"):
                    failed_videos.append({
                        'video_info': video,
                        'progress_index': i,
                        'error': progress_data[i]["Status"]
                    })
            
            if failed_videos:
                st.session_state.playlist_failed_videos = failed_videos
                st.session_state.playlist_config = config
                st.session_state.playlist_progress_data = progress_data
                st.session_state.playlist_videos_to_process = videos_to_process
                st.session_state.playlist_output_path = playlist_output_path

        # Add download all transcriptions button regardless of processing status
        if 'playlist_output_path' in st.session_state and os.path.exists(st.session_state.playlist_output_path):
            st.divider()
            st.subheader("📦 Download All Transcriptions")
            
            # Count existing transcription files
            transcript_files = []
            for root, dirs, files in os.walk(st.session_state.playlist_output_path):
                for file in files:
                    if file.endswith('.txt') and not file.startswith('_'):
                        transcript_files.append(file)
            
            if transcript_files:
                st.info(f"📄 Found {len(transcript_files)} transcription files ready for download")
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("🗜️ Create ZIP", help="Create a ZIP file with all transcriptions", key="create_zip_btn"):
                        with st.spinner("Creating ZIP file..."):
                            zip_data, file_count = create_transcriptions_zip(
                                st.session_state.playlist_output_path, 
                                st.session_state.get('playlist_title', 'playlist')
                            )
                            
                            if zip_data and file_count > 0:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                zip_filename = f"transcriptions_{sanitize_filename(playlist_title_text)}_{timestamp}.zip"
                                
                                st.session_state.zip_data = zip_data
                                st.session_state.zip_filename = zip_filename
                                st.session_state.zip_file_count = file_count
                                st.success(f"✅ ZIP file created with {file_count} transcription files!")
                            else:
                                st.error("❌ Failed to create ZIP file")
                
                with col2:
                    if 'zip_data' in st.session_state:
                        st.download_button(
                            label=f"⬇️ Download ZIP ({st.session_state.zip_file_count} files)",
                            data=st.session_state.zip_data,
                            file_name=st.session_state.zip_filename,
                            mime="application/zip",
                            help="Download ZIP file containing all transcriptions",
                            key="download_zip_btn"
                        )
            else:
                st.warning("📭 No transcription files found in the output directory")

        elif video_items is None:
             st.error("❌ Could not retrieve video list from playlist due to an error.")
        else:
             st.info("ℹ️ No videos found in the specified playlist.")
             
    except Exception as e:
        st.error(f"An unexpected error occurred during playlist processing: {e}")
        logger.error(f"Unexpected error in render_url for playlist: {e}")
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
    
    return


def render(config):
    """Render method for playlist"""
    st.header("Playlist Transcripts")
    playlist_url = st.text_input("Enter YouTube Playlist URL:")

    # Main download button
    col1, col2 = st.columns([2, 1])
    
    with col1:
        download_button = st.button("Download Playlist Transcripts", type="primary")
    
    with col2:
        # Show retry button only if there are failed videos
        retry_available = 'playlist_failed_videos' in st.session_state and st.session_state.playlist_failed_videos
        retry_button = st.button(
            f"🔄 Retry Failed ({len(st.session_state.playlist_failed_videos) if retry_available else 0})",
            disabled=not retry_available,
            help="Retry downloading videos that failed in the last playlist processing"
        )

    if download_button:
        if playlist_url:
            with st.spinner("Downloading playlist transcripts..."):
                render_url(playlist_url, config)
        else:
            st.warning("Please enter a valid YouTube Playlist URL.")
    
    if retry_button and retry_available:
        with st.spinner("Retrying failed downloads..."):
            retry_failed_videos()
    
    # Show failed videos info if available
    if retry_available:
        with st.expander(f"⚠️ Failed Videos ({len(st.session_state.playlist_failed_videos)})", expanded=False):
            failed_videos = st.session_state.playlist_failed_videos
            st.write("The following videos failed to download and can be retried:")
            
            failed_list = []
            for i, failed_video in enumerate(failed_videos):
                video_info = failed_video['video_info']
                error = failed_video['error']
                failed_list.append({
                    "#": i + 1,
                    "Title": video_info['title'][:60] + "..." if len(video_info['title']) > 60 else video_info['title'],
                    "Error": error[:100] + "..." if len(error) > 100 else error,
                    "URL": video_info['url']
                })
            
            if failed_list:
                failed_df = pd.DataFrame(failed_list)
                st.dataframe(failed_df, use_container_width=True, hide_index=True)
                
                st.info("💡 **Tips for retry:**")
                st.write("- Some videos may have temporary issues that resolve over time")
                st.write("- Age-restricted or private videos cannot be downloaded")
                st.write("- Check your internet connection if many videos failed")
                st.write("- Try adjusting the download delay in settings if rate-limited")
