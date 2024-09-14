import streamlit as st
import os
import re
import json
import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from pytube import Playlist
import PyPDF2
from docx import Document
from googletrans import Translator
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
import time
import hashlib

# Configure logging to an external file 'knowledge.log'
logging.basicConfig(
    filename='knowledge.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load and save configuration
def load_config():
    config_file = "settings.json"
    try:
        with open(config_file, 'r') as f:
            logger.info("Loading configuration from settings.json")
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Configuration file not found. Creating a new one with default settings.")
        config = {
            "download_folder": os.path.join(os.getcwd(), "Transcriptions")
        }
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return config

def save_config(config):
    with open("settings.json", 'w') as f:
        logger.info("Saving configuration to settings.json")
        json.dump(config, f)

# Helper functions
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
    try:
        video_id = get_video_id_from_url(video_url)
        if video_id is None:
            return "unknown_title"
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        video_title = transcript_list._video_title  # Access the protected member to get the title
        return sanitize_filename(video_title)
    except Exception as e:
        logger.error(f"Error fetching video title: {str(e)}")
        st.error(f"Error fetching video title: {str(e)}")
        return "unknown_title"

def fetch_transcript(video_url):
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
                translated_text = ' '.join([translator.translate(entry['text'], src='pt', dest='en').text for entry in pt_transcript])
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

def get_playlist_videos(playlist_url):
    try:
        logger.info(f"Fetching playlist videos from URL: {playlist_url}")
        playlist = Playlist(playlist_url)
        return playlist.video_urls
    except Exception as e:
        logger.error(f"Failed to fetch playlist videos: {str(e)}")
        st.error(f"Failed to fetch playlist videos: {str(e)}")
        return []

def get_channel_name_from_url(channel_url):
    parts = channel_url.split('@')
    if len(parts) > 1:
        channel_name_part = parts[-1].split('/', 1)[0]
        logger.info(f"Extracted channel name from URL: {channel_name_part}")
        return channel_name_part
    return None

def get_channel_name_from_shorts_url(shorts_url):
    match = re.search(r"youtube\.com/[@]([^/]+)/shorts", shorts_url)
    if match:
        return match.group(1)
    else:
        return "UnknownChannel"

def fetch_shorts_transcript(shorts_url):
    shorts_url = shorts_url.replace("/shorts/", "/watch?v=")
    match = re.search(r"v=([a-zA-Z0-9_-]+)", shorts_url)
    if match is None:
        return None, "Could not find a valid video ID in the URL."

    video_id = match.group(1)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en']).fetch()
        return transcript, None
    except NoTranscriptFound:
        return None, "No transcript found for the provided video ID."
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."

def fetch_videos_from_channel_selenium(channel_url):
    options = FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.get(channel_url)
    time.sleep(5)
    last_height = driver.execute_script("return document.documentElement.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    videos_data = []
    videos = driver.find_elements(By.CSS_SELECTOR, "a#video-title-link")
    for video in videos:
        video_url = video.get_attribute('href')
        video_title = video.get_attribute('title')
        videos_data.append((video_url, video_title))

    driver.quit()
    return videos_data

def fetch_videos_from_shorts_page(shorts_url):
    options = FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.get(shorts_url)
    time.sleep(5)
    last_height = driver.execute_script("return document.documentElement.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    videos_data = []
    videos = driver.find_elements(By.CSS_SELECTOR, "a.yt-simple-endpoint.style-scope.ytd-rich-grid-slim-media")
    for video in videos:
        href = video.get_attribute('href')
        title_element = video.find_element(By.ID, "video-title")
        title = title_element.text if title_element else "Unknown Title"
        videos_data.append((href, title))

    driver.quit()
    return videos_data

def download_all_shorts_transcripts(shorts_url, config):
    st.info(f"Starting download process for shorts from URL: {shorts_url}")
    logger.info(f"Starting download process for shorts from URL: {shorts_url}")
    channel_name = get_channel_name_from_shorts_url(shorts_url)
    if not channel_name:
        logger.error("Could not extract channel name from URL.")
        st.error("Could not extract channel name from URL. Please check the URL and try again.")
        return

    folder_name = os.path.join(config['download_folder'], channel_name)
    st.info(f"Downloading transcripts to folder: {folder_name}")
    logger.info(f"Downloading transcripts to folder: {folder_name}")
    create_folder(folder_name)

    shorts_data = fetch_videos_from_shorts_page(shorts_url)
    st.info(f"Found {len(shorts_data)} shorts to process.")
    logger.info(f"Found {len(shorts_data)} shorts to process.")
    if not shorts_data:
        logger.error("No shorts data found after fetching the page.")
        st.error("No shorts data found after fetching the page. Please check the URL and try again.")
        return

    progress_bar = st.progress(0)
    for i, (url, title) in enumerate(shorts_data):
        sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title)
        st.info(f"Processing short: {sanitized_title}")
        logger.info(f"Processing short: {sanitized_title}")

        video_url = f"https://www.youtube.com{url}"

        try:
            transcript, error = fetch_shorts_transcript(video_url)
            if error:
                logger.warning(f"Error downloading transcript for {sanitized_title}: {error}")
                st.warning(f"Error downloading transcript for {sanitized_title}: {error}")
                continue
            if not transcript:
                logger.warning(f"No transcript available for {sanitized_title}.")
                st.warning(f"No transcript available for {sanitized_title}.")
                continue

            save_path = save_transcript_to_text(' '.join([entry['text'] for entry in transcript]), sanitized_title, folder_name)
            st.success(f"Transcript for {sanitized_title} saved to {save_path}.")
            logger.info(f"Transcript for {sanitized_title} saved to {save_path}.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {sanitized_title}: {str(e)}")
            st.error(f"An unexpected error occurred while processing {sanitized_title}: {str(e)}")

        progress_bar.progress((i + 1) / len(shorts_data))

    st.success("All available shorts transcripts have been downloaded.")
    logger.info("All available shorts transcripts have been downloaded.")

# Main Streamlit app
def main():
    st.title("YouTube Transcript Downloader")

    global config
    config = load_config()

    # Main content area
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Single Video", "Single Short", "Channel Videos",
        "Channel Shorts", "Playlist", "File Converter"
    ])

    with tab1:
        st.header("Single Video Transcript")
        video_url = st.text_input("Enter YouTube Video URL:")
        if st.button("Download Transcript"):
            if video_url:
                with st.spinner("Downloading transcript..."):
                    logger.info(f"Downloading transcript for video URL: {video_url}")
                    transcript = fetch_transcript(video_url)
                    if transcript:
                        filename = get_video_title(video_url)
                        save_path = save_transcript_to_text(transcript, filename, config['download_folder'])
                        if save_path:
                            st.success(f"Transcript saved to {save_path}")
                            logger.info(f"Transcript saved to {save_path}")
                        else:
                            st.error("Failed to save the transcript.")
                            logger.error("Failed to save the transcript.")
                    else:
                        st.error("Failed to fetch transcript.")
                        logger.error("Failed to fetch transcript.")
            else:
                st.warning("Please enter a valid YouTube URL.")
                logger.warning("No YouTube URL entered.")

    with tab2:
        st.header("Single YouTube Short Transcript")
        shorts_url = st.text_input("Enter YouTube Shorts URL:")
        if st.button("Download Short Transcript"):
            if shorts_url:
                with st.spinner("Downloading shorts transcript..."):
                    logger.info(f"Downloading transcript for shorts URL: {shorts_url}")
                    transcript, error = fetch_shorts_transcript(shorts_url)
                    if error:
                        st.error(error)
                        logger.error(error)
                    elif transcript:
                        title = get_video_title(shorts_url)
                        save_path = save_transcript_to_text(' '.join([entry['text'] for entry in transcript]), title, config['download_folder'])
                        if save_path:
                            st.success(f"Short transcript saved to {save_path}")
                            logger.info(f"Short transcript saved to {save_path}")
                        else:
                            st.error("Failed to save the short transcript.")
                            logger.error("Failed to save the short transcript.")
                    else:
                        st.error("Failed to fetch short transcript.")
                        logger.error("Failed to fetch short transcript.")
            else:
                st.warning("Please enter a valid YouTube Shorts URL.")
                logger.warning("No YouTube Shorts URL entered.")

    with tab3:
        st.header("Channel Videos Transcripts")
        channel_url = st.text_input("Enter YouTube Channel URL:")
        if st.button("Download All Channel Video Transcripts"):
            if channel_url:
                with st.spinner("Downloading transcripts from channel..."):
                    logger.info(f"Downloading transcripts from channel URL: {channel_url}")
                    videos_data = fetch_videos_from_channel_selenium(channel_url)
                    video_urls = [video[0] for video in videos_data]
                    if video_urls:
                        progress_bar = st.progress(0)
                        for i, video_url in enumerate(video_urls):
                            transcript = fetch_transcript(video_url)
                            if transcript:
                                filename = get_video_title(video_url)
                                save_transcript_to_text(transcript, filename, config['download_folder'])
                            progress_bar.progress((i + 1) / len(video_urls))
                        st.success(f"All available video transcripts downloaded to {config['download_folder']}")
                        logger.info(f"All available video transcripts downloaded to {config['download_folder']}")
                    else:
                        st.warning("No videos found or unable to process the channel URL.")
                        logger.warning("No videos found or unable to process the channel URL.")
            else:
                st.warning("Please enter a valid YouTube Channel URL.")
                logger.warning("No YouTube Channel URL entered.")

    with tab4:
        st.header("Channel Shorts Transcripts")
        shorts_channel_url = st.text_input("Enter YouTube Shorts Channel URL:")
        if st.button("Download All Channel Shorts Transcripts"):
            if shorts_channel_url:
                with st.spinner("Downloading transcripts from shorts channel..."):
                    logger.info(f"Downloading transcripts from shorts channel URL: {shorts_channel_url}")
                    download_all_shorts_transcripts(shorts_channel_url, config)
            else:
                st.warning("Please enter a valid YouTube Shorts Channel URL.")
                logger.warning("No YouTube Shorts Channel URL entered.")

    with tab5:
        st.header("Playlist Transcripts")
        playlist_url = st.text_input("Enter YouTube Playlist URL:")
        if st.button("Download Playlist Transcripts"):
            if playlist_url:
                with st.spinner("Downloading transcripts from playlist..."):
                    logger.info(f"Downloading transcripts from playlist URL: {playlist_url}")
                    video_urls = get_playlist_videos(playlist_url)
                    if video_urls:
                        progress_bar = st.progress(0)
                        for i, video_url in enumerate(video_urls):
                            transcript = fetch_transcript(video_url)
                            if transcript:
                                filename = get_video_title(video_url)
                                save_transcript_to_text(transcript, filename, config['download_folder'])
                            progress_bar.progress((i + 1) / len(video_urls))
                        st.success(f"All available playlist transcripts downloaded to {config['download_folder']}")
                        logger.info(f"All available playlist transcripts downloaded to {config['download_folder']}")
                    else:
                        st.warning("No videos found or unable to process the playlist URL.")
                        logger.warning("No videos found or unable to process the playlist URL.")
            else:
                st.warning("Please enter a valid YouTube Playlist URL.")
                logger.warning("No YouTube Playlist URL entered.")

    with tab6:
        st.header("File Converter")
        file_type = st.radio("Select file type to convert:", ("PDF", "DOCX"))
        uploaded_file = st.file_uploader(f"Choose a {file_type} file", type=[file_type.lower()])
        if uploaded_file is not None:
            if st.button("Convert to Text"):
                with st.spinner("Converting file..."):
                    logger.info(f"Converting uploaded {file_type} file to text.")
                    if file_type == "PDF":
                        pdf_reader = PyPDF2.PdfReader(uploaded_file)
                        text_content = []
                        for page in pdf_reader.pages:
                            text_content.append(page.extract_text())
                    else:  # DOCX
                        doc = Document(uploaded_file)
                        text_content = [para.text for para in doc.paragraphs]

                    filename = os.path.splitext(uploaded_file.name)[0]
                    save_path = save_transcript_to_text("\n".join(text_content), filename, config['download_folder'])
                    if save_path:
                        st.success(f"File converted and saved to {save_path}")
                        logger.info(f"File converted and saved to {save_path}")
                    else:
                        st.error("Failed to convert and save the file.")
                        logger.error("Failed to convert and save the file.")

    # Save config at the end
    save_config(config)
    logger.info("Configuration saved.")

if __name__ == "__main__":
    main()
