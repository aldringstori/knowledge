#!/usr/bin/env python3
"""
Weekly Channel Monitor - Standalone script to check saved channels for new videos
and download transcriptions automatically.

Usage:
    python check_channels.py

Cron setup (weekly, Monday 9am):
    0 9 * * 1 cd /home/stori/knowledge && /home/stori/knowledge/venv/bin/python check_channels.py >> logs/channel_check.log 2>&1
"""

import os
import sys
import time
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logging_setup import get_module_logger
from utils.channel_manager import ChannelManager
from utils.video_database import get_video_database
from utils.common import (
    fetch_transcript,
    save_transcript_to_text,
    get_video_title,
    get_video_id_from_url,
    create_folder,
    setup_selenium_driver,
    sanitize_filename,
)
from utils.config import get_config

logger = get_module_logger("check_channels")


def fetch_channel_video_list(channel_url):
    """Fetch video URLs from a channel's /videos page using Selenium.

    Reuses the same logic as modules/channel_videos.py but without Streamlit dependencies.
    """
    from selenium.webdriver.common.by import By
    import random

    if not channel_url.endswith('/videos'):
        channel_url = channel_url.rstrip('/') + '/videos'

    driver = None
    video_urls = []

    try:
        driver = setup_selenium_driver(headless=True)
        if not driver:
            logger.error("Failed to initialize Selenium driver")
            return None

        logger.info(f"Navigating to: {channel_url}")
        driver.get(channel_url)
        time.sleep(3)

        # Scroll to load videos
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        for scroll in range(10):
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Extract video URLs
        selectors = [
            'a[href^="/watch?v="]',
            'a[id="video-title-link"]',
            'a.ytd-rich-grid-media[href*="/watch"]',
        ]

        video_links = []
        for selector in selectors:
            try:
                links = driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    video_links = links
                    break
            except Exception:
                continue

        if not video_links:
            logger.warning(f"No video links found for {channel_url}")
            return []

        seen_ids = set()
        for link in video_links:
            try:
                href = link.get_attribute('href')
                if href and '/watch?v=' in href:
                    video_id = get_video_id_from_url(href)
                    if video_id and video_id not in seen_ids:
                        seen_ids.add(video_id)
                        title = link.get_attribute('title') or link.get_attribute('aria-label') or link.text or "Unknown"
                        clean_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_urls.append({
                            "id": video_id,
                            "title": sanitize_filename(title.strip()),
                            "url": clean_url,
                        })
            except Exception:
                continue

        logger.info(f"Found {len(video_urls)} videos for {channel_url}")
        return video_urls

    except Exception as e:
        logger.error(f"Error fetching channel videos: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def check_single_channel(cm, video_db, channel_info, config):
    """Check a single channel for new videos and download transcriptions.

    Returns:
        Tuple of (new_count, skipped_count, failed_count)
    """
    channel_id = channel_info["channel_id"]
    channel_name = channel_info["name"]
    channel_url = channel_info["url"]

    print(f"\n--- Checking: {channel_name} ---")
    logger.info(f"Checking channel: {channel_name} ({channel_url})")

    videos = fetch_channel_video_list(channel_url)
    if videos is None:
        print(f"  ERROR: Failed to fetch video list")
        logger.error(f"Failed to fetch videos for {channel_name}")
        return 0, 0, 1

    new_count = 0
    skipped_count = 0
    failed_count = 0

    for video in videos:
        video_url = video["url"]
        video_title = video["title"]

        # Check both databases for duplicates
        if video_db.is_video_downloaded(video_url) or cm.is_video_downloaded(channel_id, video_url):
            skipped_count += 1
            continue

        # New video — download transcript
        print(f"  NEW: {video_title[:60]}")
        logger.info(f"Downloading transcript for: {video_title}")

        transcript = fetch_transcript(video_url, headless=True)
        if transcript:
            # Save transcript
            download_folder = config.get('download_folder', 'transcriptions')
            channel_folder = os.path.join(download_folder, sanitize_filename(channel_name))
            create_folder(channel_folder)

            file_path = save_transcript_to_text(transcript, sanitize_filename(video_title), channel_folder)

            # Mark in both databases
            video_db.add_downloaded_video(
                video_url, title=video_title, file_path=file_path,
                source_type='channel', source_url=channel_url
            )
            cm.add_downloaded_video(channel_id, video_url, video_title, file_path)

            new_count += 1
            print(f"    -> Saved: {file_path}")
        else:
            failed_count += 1
            print(f"    -> FAILED: No transcript available")
            logger.warning(f"Failed to get transcript for {video_title}")

        # Small delay between downloads
        time.sleep(config.get('download_delay_seconds', 3))

    # Update last_checked
    cm.update_last_checked(channel_id)

    print(f"  Summary: {new_count} new, {skipped_count} skipped, {failed_count} failed")
    return new_count, skipped_count, failed_count


def main():
    print(f"=== Channel Check Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    logger.info("Starting channel check run")

    config = get_config()
    cm = ChannelManager()
    video_db = get_video_database()

    due_channels = cm.get_channels_due_for_check()

    if not due_channels:
        print("No channels due for checking.")
        logger.info("No channels due for checking")
        return

    print(f"Found {len(due_channels)} channel(s) due for checking.")

    total_new = 0
    total_skipped = 0
    total_failed = 0

    for channel_info in due_channels:
        try:
            new, skipped, failed = check_single_channel(cm, video_db, channel_info, config)
            total_new += new
            total_skipped += skipped
            total_failed += failed
        except Exception as e:
            print(f"  ERROR processing {channel_info['name']}: {e}")
            logger.error(f"Error processing channel {channel_info['name']}: {e}")

    print(f"\n=== Run Complete ===")
    print(f"Total: {total_new} new transcripts, {total_skipped} skipped, {total_failed} failed")
    logger.info(f"Channel check complete: {total_new} new, {total_skipped} skipped, {total_failed} failed")


if __name__ == "__main__":
    main()
