import os
import re
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from pytube import YouTube
from deep_translator import GoogleTranslator
import streamlit as st
from .logging_setup import logger


def create_folder(folder_name):
    if not os.path.exists(folder_name):
        logger.info(f"Creating folder: {folder_name}")
        os.makedirs(folder_name)


def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '', filename)


def get_video_id_from_url(url):
    logger.info(f"Extracting video ID from URL: {url}")
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if match:
        return match.group(1)
    else:
        logger.error(f"Invalid YouTube URL: {url}")
        return None


def get_video_title(video_url):
    """Get video title using pytube with fallback to video ID."""
    try:
        yt = YouTube(video_url)
        video_title = yt.title
        return sanitize_filename(video_title)
    except Exception as e:
        logger.warning(f"Pytube failed to fetch title: {str(e)}")
        video_id = get_video_id_from_url(video_url)
        return f"video_{video_id}"


def setup_selenium_driver():
    """Setup Edge driver without headless mode for transcript scraping."""
    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        edge_options = EdgeOptions()
        # Remove headless mode to see what's happening
        # edge_options.add_argument('--headless')
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--window-size=1920,1080')
        edge_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')
        
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=edge_options)
        return driver
    except Exception as e:
        logger.warning(f"Failed to setup Edge driver: {str(e)}, falling back to Chrome")
        # Fallback to Chrome if Edge fails
        try:
            from selenium.webdriver.chrome.service import Service
            chrome_options = Options()
            # Remove headless mode to see what's happening
            # chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as chrome_error:
            logger.error(f"Failed to setup Chrome driver as fallback: {str(chrome_error)}")
            return None


def fetch_transcript(video_url, max_retries=3):
    """Fetch transcript for a video using Selenium web scraping."""
    video_id = get_video_id_from_url(video_url)
    if video_id is None:
        return None

    logger.info(f"Attempting to fetch transcript for video {video_id} using Selenium")
    
    driver = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = random.uniform(2, 5)
                logger.info(f"Retrying transcript fetch after {delay:.1f}s delay (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            
            # Setup driver
            driver = setup_selenium_driver()
            if driver is None:
                logger.error("Failed to setup Selenium driver")
                continue
            
            # Navigate to YouTube video
            driver.get(video_url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "movie_player"))
            )
            
            # Look for transcript button - try multiple selectors
            transcript_selectors = [
                "button[aria-label*='transcript']",
                "button[aria-label*='Transcript']",
                "yt-button-shape[aria-label*='transcript']",
                "yt-button-shape[aria-label*='Transcript']",
                "[data-tooltip-target-id*='transcript']"
            ]
            
            transcript_button = None
            for selector in transcript_selectors:
                try:
                    transcript_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if transcript_button is None:
                logger.warning(f"No transcript button found for video {video_id}")
                # Try to find transcript in description or comments
                transcript_text = extract_transcript_from_page(driver)
                if transcript_text:
                    return transcript_text
                continue
            
            # Click transcript button
            driver.execute_script("arguments[0].click();", transcript_button)
            time.sleep(2)
            
            # Wait for transcript panel to appear
            transcript_panel_selectors = [
                "ytd-transcript-segment-list-renderer",
                "[data-target-id='engagement-panel-transcript']",
                ".ytd-transcript-segment-renderer"
            ]
            
            transcript_segments = []
            for panel_selector in transcript_panel_selectors:
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, panel_selector))
                    )
                    
                    # Extract transcript segments
                    segments = driver.find_elements(By.CSS_SELECTOR, "ytd-transcript-segment-renderer .segment-text")
                    if not segments:
                        segments = driver.find_elements(By.CSS_SELECTOR, ".ytd-transcript-segment-renderer")
                    
                    for segment in segments:
                        text = segment.get_attribute('textContent') or segment.text
                        if text and text.strip():
                            transcript_segments.append(text.strip())
                    
                    if transcript_segments:
                        break
                        
                except TimeoutException:
                    continue
            
            if transcript_segments:
                transcript_text = ' '.join(transcript_segments)
                logger.info(f"Successfully extracted transcript with {len(transcript_text)} characters")
                return transcript_text
            else:
                logger.warning(f"No transcript segments found for video {video_id}")
                
        except Exception as e:
            logger.error(f"Selenium error for video {video_id} (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    # If all attempts fail
    logger.error(f"All transcript extraction attempts failed for video {video_id}")
    st.error(f"Unable to fetch transcript for video {video_id}: All retry attempts failed")
    return None


def extract_transcript_from_page(driver):
    """Try to extract transcript from video description or other page elements."""
    try:
        # Look for transcript in description
        description_selectors = [
            "#description ytd-text-inline-expander-renderer",
            "#description .content",
            "ytd-video-secondary-info-renderer #description"
        ]
        
        for selector in description_selectors:
            try:
                description_element = driver.find_element(By.CSS_SELECTOR, selector)
                description_text = description_element.text
                
                # Check if description contains transcript-like content
                if len(description_text) > 500 and ('transcript' in description_text.lower() or 
                    description_text.count('.') > 10):  # Heuristic for transcript-like content
                    logger.info("Found transcript-like content in video description")
                    return description_text
            except NoSuchElementException:
                continue
                
    except Exception as e:
        logger.warning(f"Failed to extract transcript from page elements: {str(e)}")
    
    return None


def save_transcript_to_text(transcript, filename, folder):
    """Save transcript to a text file."""
    if transcript is None:
        logger.warning(f"No transcript available to save for {filename}.")
        st.warning(f"No transcript available to save for {filename}.")
        return None

    if not os.path.exists(folder):
        create_folder(folder)
    file_path = os.path.join(folder, f"{filename}.txt")
    logger.info(f"Saving transcript to {file_path}")

    with open(file_path, "w", encoding='utf-8') as file:
        file.write(transcript)

    return file_path