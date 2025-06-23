
import streamlit as st
import pandas as pd
from utils.logging_setup import get_channel_shorts_logger

# Get module-specific logger
logger = get_channel_shorts_logger()
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url
)
import os
import re
import time


def get_channel_name(url):
    """Extract channel name from URL"""
    match = re.search(r'youtube\.com/[@]?([^/]+)/?', url)
    return match.group(1) if match else "UnknownChannel"


def convert_shorts_urls(shorts_data):
    """Convert shorts URLs - functionality not available"""
    st.error("YouTube Shorts processing is not available in this version")
    logger.error("Shorts processing not available - browser automation removed")
    return None


def download_transcripts(converted_data, folder_name):
    """Download transcripts - functionality not available"""
    st.error("YouTube Shorts transcript downloading is not available in this version")
    logger.error("Shorts transcript downloading not available - browser automation removed")
    return []


def display_table(data, container, step):
    """Display table - functionality not available"""
    pass


def collect_shorts_urls(channel_url):
    """Shorts collection - functionality not available"""
    st.error("YouTube Shorts URL collection is not available in this version")
    logger.error("Shorts collection not available - browser automation removed")
    return []


def process_shorts_channel(channel_url: str, config: dict):
    """Process a shorts channel in three steps"""
    try:
        logger.info("Starting shorts channel processing")
        logger.info(f"Channel URL: {channel_url}")

        # Create folder
        channel_name = get_channel_name(channel_url)
        logger.info(f"Channel name extracted: {channel_name}")
        folder_name = os.path.join(config['download_folder'], f"{channel_name}_shorts")
        logger.info(f"Creating folder: {folder_name}")
        create_folder(folder_name)

        # Step 1: Collect shorts URLs
        logger.info("Starting Step 1: Collecting Shorts URLs")
        st.subheader("Step 1: Collecting Shorts URLs")
        shorts_data = collect_shorts_urls(channel_url)

        if not shorts_data:
            logger.error("No shorts found in channel")
            st.error("No shorts found in channel")
            return False

        logger.info(f"Step 1 complete: Found {len(shorts_data)} shorts")
        st.success(f"Found {len(shorts_data)} shorts")

        # Step 2: Convert URLs
        logger.info("Starting Step 2: Converting URLs")
        st.subheader("Step 2: Converting URLs")
        converted_data = convert_shorts_urls(shorts_data)

        if not converted_data:
            logger.error("Failed to convert any URLs")
            st.error("Failed to convert any URLs")
            return False

        logger.info(f"Step 2 complete: Converted {len(converted_data)} URLs")
        st.success(f"Successfully converted {len(converted_data)} URLs")

        # Step 3: Download transcripts
        logger.info("Starting Step 3: Downloading Transcripts")
        st.subheader("Step 3: Downloading Transcripts")
        download_status = download_transcripts(converted_data, folder_name)

        successful = sum(1 for s in download_status if s['status'] == '✅')
        logger.info(f"Step 3 complete: Successfully downloaded {successful} transcripts")

        if successful > 0:
            st.success(f"Successfully downloaded {successful} out of {len(download_status)} transcripts")

            # Offer to save report
            if st.button("Download Summary Report"):
                report_path = os.path.join(folder_name, f"{channel_name}_report.csv")
                pd.DataFrame(download_status).to_csv(report_path, index=False)
                logger.info(f"Saved summary report to: {report_path}")
                st.success(f"Summary report saved to {report_path}")

            return True
        else:
            logger.error("Failed to download any transcripts")
            st.error("Failed to download any transcripts")
            return False

    except Exception as e:
        logger.error(f"Error processing shorts channel: {str(e)}")
        st.error(f"Error processing shorts channel: {str(e)}")
        return False


def render_url(channel_url: str, config: dict):
    """Process a channel URL"""
    logger.info(f"Starting render_url for channel: {channel_url}")
    success = process_shorts_channel(channel_url, config)
    logger.info(f"Processing completed with success: {success}")
    return success


def render(config):
    """Render method for channel shorts"""
    st.header("Channel Shorts Transcripts")
    channel_url = st.text_input("Enter YouTube Channel Shorts URL:")

    if st.button("Download Channel Shorts"):
        if channel_url:
            logger.info(f"Starting processing for URL: {channel_url}")
            with st.spinner("Processing shorts channel..."):
                success = render_url(channel_url, config)
                if not success:
                    logger.error("Processing failed")
                    st.error("Failed to process channel shorts. Check the logs for details.")
        else:
            logger.warning("No URL provided")
            st.warning("Please enter a valid YouTube Channel Shorts URL.")