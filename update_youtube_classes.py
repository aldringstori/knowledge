#!/usr/bin/env python3
"""
YouTube Class Name Update Script

This script automatically detects and updates YouTube's dynamic class names
for transcript extraction elements. It handles the multi-step process:
1. Click "Show more" button to expand description
2. Click "Show transcript" button 
3. Extract transcript content from the panel
4. Update .env file with current class names

Usage: python update_youtube_classes.py [video_url]
"""

import os
import sys
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv, set_key
import random

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_class_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YouTubeClassUpdater:
    def __init__(self, headless=True):
        """Initialize the YouTube class updater"""
        self.driver = None
        self.headless = headless
        self.env_file = '.env'
        
        # Default selectors and class names
        self.selectors = {
            'show_more_button': {
                'selectors': [
                    '//tp-yt-paper-button[@id="expand"]',
                    '//button[contains(text(), "...mais")]',
                    '//button[contains(text(), "Show more")]',
                    '//button[contains(text(), "...more")]',
                    '.ytd-text-inline-expander #expand'
                ],
                'env_key': 'YOUTUBE_SHOW_MORE_BUTTON_CLASS'
            },
            'show_transcript_button': {
                'selectors': [
                    '//button[contains(text(), "Show transcript")]',
                    '//button[contains(text(), "Mostrar transcrição")]',
                    '//button[contains(text(), "Transcript")]',
                    '//yt-button-shape[contains(@aria-label, "transcript")]',
                    '[aria-label*="transcript" i]'
                ],
                'env_key': 'YOUTUBE_SHOW_TRANSCRIPT_BUTTON_CLASS'
            },
            'transcript_panel': {
                'selectors': [
                    'ytd-transcript-search-panel-renderer',
                    'ytd-transcript-renderer',
                    '[data-target-id="engagement-panel-transcript"]'
                ],
                'env_key': 'YOUTUBE_TRANSCRIPT_PANEL_CLASS'
            },
            'transcript_segments': {
                'selectors': [
                    'yt-formatted-string.segment-text',
                    '.segment-text',
                    'ytd-transcript-segment-renderer .segment-text'
                ],
                'env_key': 'YOUTUBE_TRANSCRIPT_SEGMENTS_CLASS'
            }
        }

    def setup_driver(self):
        """Setup Chrome WebDriver with options to avoid detection"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument('--headless')
                
            # Anti-detection options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Realistic user agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            return False

    def load_page(self, url):
        """Load YouTube video page and wait for it to be ready"""
        try:
            logger.info(f"Loading page: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "ytd-watch-flexy"))
            )
            
            # Random delay to mimic human behavior
            time.sleep(random.uniform(2, 4))
            logger.info("Page loaded successfully")
            return True
            
        except TimeoutException:
            logger.error("Page load timeout")
            return False
        except Exception as e:
            logger.error(f"Error loading page: {str(e)}")
            return False

    def find_element_with_selectors(self, element_name, selectors):
        """Try multiple selectors to find an element"""
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    # XPath selector
                    element = self.driver.find_element(By.XPATH, selector)
                else:
                    # CSS selector
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                logger.info(f"Found {element_name} using selector: {selector}")
                return element, selector
                
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.warning(f"Error with selector {selector}: {str(e)}")
                continue
        
        logger.warning(f"Could not find {element_name} with any selector")
        return None, None

    def click_show_more_button(self):
        """Click the 'Show more' button to expand description"""
        try:
            logger.info("Looking for 'Show more' button...")
            
            element, selector = self.find_element_with_selectors(
                "show more button", 
                self.selectors['show_more_button']['selectors']
            )
            
            if element:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(1)
                
                # Try to click
                self.driver.execute_script("arguments[0].click();", element)
                logger.info("'Show more' button clicked successfully")
                
                # Update .env with working selector
                self.update_env_class('show_more_button', selector)
                
                time.sleep(random.uniform(1, 2))
                return True
            else:
                logger.warning("'Show more' button not found or not needed")
                return False
                
        except Exception as e:
            logger.error(f"Error clicking 'Show more' button: {str(e)}")
            return False

    def click_show_transcript_button(self):
        """Click the 'Show transcript' button"""
        try:
            logger.info("Looking for 'Show transcript' button...")
            
            element, selector = self.find_element_with_selectors(
                "show transcript button",
                self.selectors['show_transcript_button']['selectors']
            )
            
            if element:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(1)
                
                # Try to click
                self.driver.execute_script("arguments[0].click();", element)
                logger.info("'Show transcript' button clicked successfully")
                
                # Update .env with working selector
                self.update_env_class('show_transcript_button', selector)
                
                time.sleep(random.uniform(2, 3))
                return True
            else:
                logger.error("'Show transcript' button not found")
                return False
                
        except Exception as e:
            logger.error(f"Error clicking 'Show transcript' button: {str(e)}")
            return False

    def extract_transcript_content(self):
        """Extract transcript content from the panel"""
        try:
            logger.info("Looking for transcript panel...")
            
            # Wait for transcript panel to appear
            panel_element = None
            for selector in self.selectors['transcript_panel']['selectors']:
                try:
                    panel_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"Found transcript panel using: {selector}")
                    self.update_env_class('transcript_panel', selector)
                    break
                except TimeoutException:
                    continue
            
            if not panel_element:
                logger.error("Transcript panel not found")
                return None
            
            # Extract transcript segments
            segments = []
            for selector in self.selectors['transcript_segments']['selectors']:
                try:
                    if selector.startswith('//'):
                        segment_elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        segment_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if segment_elements:
                        logger.info(f"Found {len(segment_elements)} transcript segments using: {selector}")
                        self.update_env_class('transcript_segments', selector)
                        
                        for element in segment_elements:
                            text = element.get_attribute('textContent') or element.text
                            if text and text.strip():
                                segments.append(text.strip())
                        break
                except Exception as e:
                    logger.warning(f"Error with segment selector {selector}: {str(e)}")
                    continue
            
            if segments:
                transcript_text = ' '.join(segments)
                logger.info(f"Successfully extracted transcript with {len(segments)} segments")
                return transcript_text
            else:
                logger.error("No transcript segments found")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting transcript: {str(e)}")
            return None

    def update_env_class(self, element_name, selector):
        """Update .env file with working selector"""
        try:
            env_key = self.selectors[element_name]['env_key']
            current_value = os.getenv(env_key, '')
            
            if current_value != selector:
                set_key(self.env_file, env_key, selector)
                logger.info(f"Updated {env_key} = {selector}")
            else:
                logger.info(f"{env_key} already up to date")
                
        except Exception as e:
            logger.error(f"Error updating .env file: {str(e)}")

    def run_update(self, video_url):
        """Main method to run the class update process"""
        try:
            if not self.setup_driver():
                return False
            
            if not self.load_page(video_url):
                return False
            
            # Step 1: Click "Show more" button (optional)
            self.click_show_more_button()
            
            # Step 2: Click "Show transcript" button
            if not self.click_show_transcript_button():
                logger.error("Failed to open transcript panel")
                return False
            
            # Step 3: Extract transcript content
            transcript = self.extract_transcript_content()
            if transcript:
                logger.info("Transcript extraction successful")
                logger.info(f"Transcript preview: {transcript[:200]}...")
                return True
            else:
                logger.error("Failed to extract transcript")
                return False
                
        except Exception as e:
            logger.error(f"Error in run_update: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

def main():
    """Main function"""
    # Default test video URL (replace with actual URL)
    default_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    if len(sys.argv) > 1:
        video_url = sys.argv[1]
    else:
        video_url = input(f"Enter YouTube video URL (or press Enter for default): ").strip()
        if not video_url:
            video_url = default_url
    
    logger.info(f"Starting YouTube class update for: {video_url}")
    
    # Ask for headless mode
    headless_choice = input("Run in headless mode? (y/n, default=n): ").strip().lower()
    headless = headless_choice in ['y', 'yes']
    
    updater = YouTubeClassUpdater(headless=headless)
    success = updater.run_update(video_url)
    
    if success:
        logger.info("YouTube class update completed successfully")
        print("✅ Update completed successfully! Check the .env file for updated selectors.")
    else:
        logger.error("YouTube class update failed")
        print("❌ Update failed. Check the log file for details.")

if __name__ == "__main__":
    main()