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


def get_video_title(video_url, headless=False):
    """Get video title using Selenium with fallback to pytube, then video ID."""
    from .config import get_config
    
    # Get configuration
    config = get_config()
    title_selector = config.get('youtube_video_title_class', 'span.style-scope.yt-formatted-string')
    
    # Try Selenium first for reliable title extraction
    driver = None
    try:
        logger.info(f"Extracting video title using Selenium for URL: {video_url}")
        
        # Setup driver
        driver = setup_selenium_driver(
            headless=headless,
            use_gpu=config.get('selenium_use_gpu', True),
            window_size=config.get('selenium_window_size', '1920,1080'),
            user_agent=config.get('selenium_user_agent')
        )
        
        if driver is None:
            raise Exception("Failed to setup Selenium driver")
        
        # Navigate to video page
        driver.get(video_url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "content"))
        )
        
        # Try multiple selectors for the video title
        title_selectors = [
            title_selector,  # From config
            'span.style-scope.yt-formatted-string',  # Primary selector
            'h1.title.style-scope.ytd-video-primary-info-renderer',
            'h1.style-scope.ytd-video-primary-info-renderer',
            '#container h1',
            'ytd-video-primary-info-renderer h1',
            'h1 yt-formatted-string',
            'h1[class*="title"]'
        ]
        
        for selector in title_selectors:
            try:
                # Look for title elements
                title_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in title_elements:
                    try:
                        # Get text content
                        title_text = element.get_attribute('textContent') or element.text
                        if title_text and title_text.strip():
                            title_text = title_text.strip()
                            # Verify this looks like a video title (not too short, not a UI element)
                            if len(title_text) > 3 and not any(ui_text in title_text.lower() for ui_text in 
                                ['share', 'save', 'like', 'subscribe', 'settings', 'autoplay']):
                                logger.info(f"Successfully extracted title with Selenium: {title_text[:50]}...")
                                return sanitize_filename(title_text)
                    except Exception as e:
                        logger.debug(f"Error extracting text from title element: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with title selector {selector}: {e}")
                continue
        
        logger.warning("No title found with Selenium, falling back to pytube")
        
    except Exception as e:
        logger.warning(f"Selenium title extraction failed: {str(e)}, falling back to pytube")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Fallback to pytube
    try:
        logger.info("Attempting to get title using pytube")
        yt = YouTube(video_url)
        video_title = yt.title
        if video_title:
            logger.info(f"Successfully extracted title with pytube: {video_title[:50]}...")
            return sanitize_filename(video_title)
    except Exception as e:
        logger.warning(f"Pytube failed to fetch title: {str(e)}")
    
    # Final fallback to video ID
    video_id = get_video_id_from_url(video_url)
    logger.warning(f"Using video ID as filename: video_{video_id}")
    return f"video_{video_id}"


def setup_selenium_driver(headless=False, use_gpu=True, window_size="1920,1080", user_agent=None):
    """Setup Edge driver with configurable options for transcript scraping."""
    from .config import get_config
    
    # Get configuration from environment variables
    config = get_config()
    
    # Use parameters or fall back to config values
    if user_agent is None:
        user_agent = config.get('selenium_user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        edge_options = EdgeOptions()
        
        # Configure headless mode
        if headless:
            edge_options.add_argument('--headless')
            logger.info("Edge driver configured in headless mode")
        else:
            logger.info("Edge driver configured in visible mode")
        
        # Basic security options
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        
        # GPU configuration
        if use_gpu and config.get('selenium_use_gpu', True):
            # Enable GPU acceleration
            edge_options.add_argument('--enable-gpu')
            edge_options.add_argument('--enable-gpu-rasterization')
            edge_options.add_argument('--enable-gpu-memory-buffer-video-frames')
            logger.info("Edge driver configured with GPU acceleration enabled")
        else:
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument('--disable-gpu-sandbox')
            logger.info("Edge driver configured with GPU acceleration disabled")
        
        # Window and user agent configuration
        edge_options.add_argument(f'--window-size={window_size}')
        edge_options.add_argument(f'--user-agent={user_agent}')
        
        # Performance optimizations
        edge_options.add_argument('--disable-extensions')
        edge_options.add_argument('--disable-plugins')
        edge_options.add_argument('--disable-images')  # Faster loading for transcript extraction
        
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=edge_options)
        return driver
        
    except Exception as e:
        logger.warning(f"Failed to setup Edge driver: {str(e)}, falling back to Chrome")
        # Fallback to Chrome if Edge fails
        try:
            from selenium.webdriver.chrome.service import Service
            chrome_options = Options()
            
            # Configure headless mode
            if headless:
                chrome_options.add_argument('--headless')
                logger.info("Chrome driver configured in headless mode")
            else:
                logger.info("Chrome driver configured in visible mode")
            
            # Basic security options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # GPU configuration
            if use_gpu and config.get('selenium_use_gpu', True):
                # Enable GPU acceleration
                chrome_options.add_argument('--enable-gpu')
                chrome_options.add_argument('--enable-gpu-rasterization')
                chrome_options.add_argument('--enable-gpu-memory-buffer-video-frames')
                logger.info("Chrome driver configured with GPU acceleration enabled")
            else:
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-gpu-sandbox')
                logger.info("Chrome driver configured with GPU acceleration disabled")
            
            # Window and user agent configuration
            chrome_options.add_argument(f'--window-size={window_size}')
            chrome_options.add_argument(f'--user-agent={user_agent}')
            
            # Performance optimizations
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Faster loading for transcript extraction
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
            
        except Exception as chrome_error:
            logger.error(f"Failed to setup Chrome driver as fallback: {str(chrome_error)}")
            return None


def fetch_transcript(video_url, max_retries=None, headless=False):
    """Fetch transcript for a video using Selenium web scraping with new extraction method."""
    from .config import get_config
    
    # Get configuration from environment variables
    config = get_config()
    
    # Use config values if not provided
    if max_retries is None:
        max_retries = config.get('max_transcript_retries', 3)
    
    retry_delay_min = config.get('browser_retry_delay_min', 2.0)
    retry_delay_max = config.get('browser_retry_delay_max', 5.0)
    
    video_id = get_video_id_from_url(video_url)
    if video_id is None:
        return None

    logger.info(f"Attempting to fetch transcript for video {video_id} using new Selenium method (headless={headless}, max_retries={max_retries})")
    
    driver = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = random.uniform(retry_delay_min, retry_delay_max)
                logger.info(f"Retrying transcript fetch after {delay:.1f}s delay (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            
            # Setup driver with configuration from environment
            driver = setup_selenium_driver(
                headless=headless,
                use_gpu=config.get('selenium_use_gpu', True),
                window_size=config.get('selenium_window_size', '1920,1080'),
                user_agent=config.get('selenium_user_agent')
            )
            if driver is None:
                logger.error("Failed to setup Selenium driver")
                continue
            
            # Navigate to YouTube video (don't wait for video player)
            driver.get(video_url)
            
            # Wait for page to load - just check for basic page structure
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "content"))
            )
            
            # Step 1: Click "Show More" button to expand description
            logger.info("Step 1: Looking for 'Show More' button...")
            expand_button = None
            expand_selectors = [
                "tp-yt-paper-button[id='expand']",
                "#expand",
                "tp-yt-paper-button.button.style-scope.ytd-text-inline-expander",
                "button[aria-label*='Show more']",
                "//tp-yt-paper-button[contains(text(), '...mais')]",
                "//tp-yt-paper-button[contains(text(), '...more')]"
            ]
            
            for selector in expand_selectors:
                try:
                    if selector.startswith('//'):
                        expand_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        expand_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    logger.info(f"Found expand button using selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if expand_button:
                logger.info("Clicking 'Show More' button...")
                driver.execute_script("arguments[0].click();", expand_button)
                time.sleep(2)  # Wait for description to expand
            else:
                logger.info("No 'Show More' button found, continuing...")
            
            # Step 2: Look for and click transcript button
            logger.info("Step 2: Looking for transcript button...")
            transcript_button = None
            transcript_selectors = [
                "//button[contains(text(), 'Show transcript')]",
                "//button[contains(text(), 'Mostrar transcrição')]", 
                "//button[contains(text(), 'transcript')]",
                "button[aria-label*='transcript']",
                "button[aria-label*='Transcript']",
                "[data-tooltip-target-id*='transcript']",
                ".yt-spec-touch-feedback-shape",
                "ytd-button-renderer button"
            ]
            
            for selector in transcript_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        try:
                            # Check if element text contains transcript-related keywords
                            element_text = element.get_attribute('innerText') or element.text or ""
                            aria_label = element.get_attribute('aria-label') or ""
                            
                            if any(keyword in (element_text + aria_label).lower() for keyword in 
                                   ['transcript', 'transcrição', 'mostrar transcrição', 'show transcript']):
                                transcript_button = element
                                logger.info(f"Found transcript button: {element_text[:50]}...")
                                break
                        except:
                            continue
                    
                    if transcript_button:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            if transcript_button is None:
                logger.warning(f"No transcript button found for video {video_id}")
                continue
            
            # Click transcript button
            logger.info("Clicking transcript button...")
            driver.execute_script("arguments[0].click();", transcript_button)
            time.sleep(3)  # Wait for transcript panel to load
            
            # Step 3: Extract transcript segments - use new extraction method
            logger.info("Step 3: Extracting transcript segments...")
            
            # Wait for transcript panel to appear
            transcript_container_selectors = [
                "ytd-transcript-segment-list-renderer",
                "div[id='segments-container']",
                config.get('youtube_transcript_panel_class', 'ytd-transcript-search-panel-renderer'),
                "ytd-transcript-segment-list-renderer",
                "[data-target-id='engagement-panel-transcript']",
                ".ytd-transcript-segment-renderer",
                "ytd-transcript-search-panel-renderer"
            ]
            
            transcript_text_segments = []
            
            # Wait for transcript container to appear
            container_found = False
            for container_selector in transcript_container_selectors:
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
                    )
                    logger.info(f"Found transcript container with selector: {container_selector}")
                    container_found = True
                    break
                except TimeoutException:
                    continue
            
            if not container_found:
                logger.warning("No transcript container found")
                continue
            
            # Extract transcript segments using the new method
            segment_selectors = [
                "yt-formatted-string.segment-text.style-scope.ytd-transcript-segment-renderer",
                "yt-formatted-string.segment-text",
                config.get('youtube_transcript_segments_class', 'yt-formatted-string.segment-text'),
                ".segment-text",
                "ytd-transcript-segment-renderer yt-formatted-string"
            ]
            
            for seg_selector in segment_selectors:
                try:
                    # Find all segment elements
                    segments = driver.find_elements(By.CSS_SELECTOR, seg_selector)
                    logger.info(f"Found {len(segments)} transcript segments with selector: {seg_selector}")
                    
                    if segments:
                        for segment in segments:
                            try:
                                # Extract text content (ignore timestamps)
                                text = segment.get_attribute('textContent') or segment.text
                                if text and text.strip():
                                    # Clean up the text
                                    cleaned_text = text.strip()
                                    if cleaned_text and len(cleaned_text) > 1:  # Ignore single characters
                                        transcript_text_segments.append(cleaned_text)
                                        logger.debug(f"Extracted segment: {cleaned_text[:50]}...")
                            except Exception as e:
                                logger.debug(f"Error extracting segment text: {e}")
                                continue
                        
                        if transcript_text_segments:
                            logger.info(f"Successfully extracted {len(transcript_text_segments)} transcript segments")
                            break
                            
                except Exception as e:
                    logger.debug(f"Error with segment selector {seg_selector}: {e}")
                    continue
            
            if transcript_text_segments:
                # Join all segments into a single transcript
                transcript_text = ' '.join(transcript_text_segments)
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