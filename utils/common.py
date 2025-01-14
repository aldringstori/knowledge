import os
import re
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import time
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from pytube import YouTube
from googletrans import Translator
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


def get_video_title_selenium(video_url):
    """Get video title using Selenium as a fallback when pytube fails."""
    try:
        options = FirefoxOptions()
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)
        driver.get(video_url)
        time.sleep(2)

        title = driver.title
        if " - YouTube" in title:
            title = title.replace(" - YouTube", "")

        driver.quit()
        return sanitize_filename(title)
    except Exception as e:
        logger.error(f"Error fetching video title with Selenium: {str(e)}")
        video_id = get_video_id_from_url(video_url)
        return f"video_{video_id}"


def get_video_title(video_url):
    """Get video title with fallback mechanisms."""
    try:
        yt = YouTube(video_url)
        video_title = yt.title
        return sanitize_filename(video_title)
    except Exception as e:
        logger.warning(f"Pytube failed to fetch title, trying Selenium: {str(e)}")
        return get_video_title_selenium(video_url)


def fetch_transcript(video_url):
    """Fetch transcript for a video with language fallback."""
    video_id = get_video_id_from_url(video_url)
    if video_id is None:
        return None

    translator = Translator()
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['en']).fetch()
            logger.info(f"Fetched English transcript for video {video_id}")
            return ' '.join([entry['text'] for entry in transcript])
        except NoTranscriptFound:
            logger.warning(f"No English transcript found for video {video_id}")
            try:
                pt_transcript = transcript_list.find_transcript(['pt']).fetch()
                translated_text = ' '.join(
                    [translator.translate(entry['text'], src='pt', dest='en').text for entry in pt_transcript])
                logger.info(f"Translated Portuguese transcript for video {video_id}")
                return translated_text
            except Exception as e:
                logger.error(f"Failed to fetch or translate Portuguese transcript for video {video_id}: {str(e)}")
                st.error(f"Failed to fetch or translate Portuguese transcript for video {video_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Unable to fetch any transcripts for video {video_id}: {str(e)}")
        st.error(f"Unable to fetch any transcripts for video {video_id}: {str(e)}")
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