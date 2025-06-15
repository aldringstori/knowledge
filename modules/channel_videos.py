import streamlit as st
import pandas as pd
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    get_video_id_from_url
)
from utils.table_utils import render_with_progress
import os
import re
import time


def get_channel_name(url):
    """Extract channel name from URL"""
    match = re.search(r'youtube\.com/[@]?([^/]+)/?', url)
    return match.group(1) if match else "UnknownChannel"


def fetch_channel_videos(channel_url):
    """Channel video extraction - functionality not available"""
    st.error("YouTube Channel video extraction is not available in this version")
    logger.error("Channel video extraction not available - browser automation removed")
    return None


def render_url(channel_url: str, config: dict):
    """Process a channel URL - maintained for backward compatibility"""
    config['name_extractor'] = get_channel_name
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