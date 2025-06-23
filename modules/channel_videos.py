import streamlit as st
import pandas as pd
from utils.logging_setup import get_channel_videos_logger

# Get module-specific logger
logger = get_channel_videos_logger()
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url,
    setup_selenium_driver
)
from utils.table_utils import render_with_progress
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import re
import time
import random


def get_channel_name(url):
    """Extract channel name from different YouTube URL formats"""
    # Handle @username format
    match = re.search(r'youtube\.com/@([^/]+)', url)
    if match:
        return match.group(1)
    
    # Handle /c/channelName format 
    match = re.search(r'youtube\.com/c/([^/]+)', url)
    if match:
        return match.group(1)
    
    # Handle /user/username format
    match = re.search(r'youtube\.com/user/([^/]+)', url)
    if match:
        return match.group(1)
    
    # Handle /channel/UCxxxxx format - extract channel ID
    match = re.search(r'youtube\.com/channel/([^/]+)', url)
    if match:
        return match.group(1)
    
    # Fallback for any other format
    match = re.search(r'youtube\.com/([^/]+)', url)
    return match.group(1) if match else "UnknownChannel"


def fetch_channel_videos(channel_url):
    """Extract video URLs from a YouTube channel using Selenium"""
    logger.info(f"Starting channel video extraction for: {channel_url}")
    
    # Ensure URL points to /videos endpoint
    if not channel_url.endswith('/videos'):
        if channel_url.endswith('/'):
            channel_url += 'videos'
        else:
            channel_url += '/videos'
    
    logger.info(f"Channel videos URL: {channel_url}")
    
    driver = None
    video_urls = []
    
    try:
        # Setup Selenium driver
        driver = setup_selenium_driver(headless=False)
        if not driver:
            logger.error("Failed to initialize Selenium driver")
            st.error("Failed to initialize browser driver")
            return None
        
        logger.info("Navigating to channel videos page...")
        driver.get(channel_url)
        
        # Wait for initial page load
        time.sleep(3)
        
        # Scroll to load more videos (YouTube uses lazy loading)
        logger.info("Scrolling to load videos...")
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 10  # Limit scrolling to prevent infinite loops
        
        while scroll_attempts < max_scrolls:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(random.uniform(2, 4))  # Random delay to appear more human-like
            
            # Check if new content loaded
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                logger.info(f"No new content loaded after scroll {scroll_attempts + 1}")
                break
                
            last_height = new_height
            scroll_attempts += 1
            logger.info(f"Scrolled {scroll_attempts}/{max_scrolls} times")
        
        # Extract video URLs using multiple selectors
        video_link_selectors = [
            'a[href^="/watch?v="]',  # Primary selector
            'a[id="video-title-link"]',  # Alternative selector
            'a.ytd-rich-grid-media[href*="/watch"]'  # Grid layout selector
        ]
        
        video_links = []
        for selector in video_link_selectors:
            try:
                links = driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    logger.info(f"Found {len(links)} video links using selector: {selector}")
                    video_links.extend(links)
                    break  # Use first successful selector
            except Exception as e:
                logger.warning(f"Selector {selector} failed: {str(e)}")
                continue
        
        if not video_links:
            logger.error("No video links found with any selector")
            st.error("No videos found on this channel page")
            return None
        
        # Extract unique video URLs and titles
        seen_video_ids = set()
        for link in video_links:
            try:
                href = link.get_attribute('href')
                if href and '/watch?v=' in href:
                    # Extract video ID to avoid duplicates
                    video_id = get_video_id_from_url(href)
                    if video_id and video_id not in seen_video_ids:
                        seen_video_ids.add(video_id)
                        
                        # Try to get video title
                        title = "Unknown Title"
                        try:
                            # Try different title extraction methods
                            title_element = link.get_attribute('title')
                            if not title_element:
                                title_element = link.get_attribute('aria-label')
                            if not title_element:
                                title_element = link.text
                            if title_element:
                                title = title_element.strip()
                        except Exception as e:
                            logger.warning(f"Could not extract title for video {video_id}: {str(e)}")
                        
                        # Clean URL (remove additional parameters)
                        clean_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_urls.append({
                            "id": video_id,
                            "title": sanitize_filename(title),
                            "url": clean_url,
                            "type": "video"
                        })
            except Exception as e:
                logger.warning(f"Error processing video link: {str(e)}")
                continue
        
        logger.info(f"Successfully extracted {len(video_urls)} unique video URLs")
        return video_urls
        
    except Exception as e:
        logger.error(f"Error during channel video extraction: {str(e)}")
        st.error(f"Error extracting channel videos: {str(e)}")
        return None
        
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser driver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing driver: {str(e)}")


def render_url(channel_url: str, config: dict):
    """Process a channel URL and extract all video transcripts"""
    logger.info(f"Processing channel URL: {channel_url}")
    
    # Set up channel-specific configuration
    config['name_extractor'] = get_channel_name
    
    # Use render_with_progress to handle the entire process
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