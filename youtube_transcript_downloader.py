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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load and save configuration
def load_config():
    config_file = "settings.json"
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        config = {
            "download_folder": os.path.join(os.getcwd(), "Transcriptions")
        }
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return config

def save_config(config):
    with open("settings.json", 'w') as f:
        json.dump(config, f)

# Helper functions
def create_folder(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '', filename)

def get_video_id_from_url(url):
    return re.search(r"v=([a-zA-Z0-9_-]+)", url).group(1)

def get_video_title(video_url):
    try:
        video_id = get_video_id_from_url(video_url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript[0]['video_id']
    except Exception:
        return "unknown_title"

def fetch_transcript(video_url):
    video_id = get_video_id_from_url(video_url)
    translator = Translator()

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['en']).fetch()
            return ' '.join([entry['text'] for entry in transcript])
        except NoTranscriptFound:
            try:
                pt_transcript = transcript_list.find_transcript(['pt']).fetch()
                translated_text = ' '.join([translator.translate(entry['text'], src='pt', dest='en').text for entry in pt_transcript])
                return translated_text
            except Exception as e:
                st.error(f"Failed to fetch or translate Portuguese transcript for video {video_id}: {str(e)}")
    except Exception as e:
        st.error(f"Unable to fetch any transcripts for video {video_id}: {str(e)}")
        return None

def save_transcript_to_text(transcript, filename, folder):
    if transcript is None:
        st.warning(f"No transcript available to save for {filename}.")
        return None

    if not os.path.exists(folder):
        create_folder(folder)
    file_path = os.path.join(folder, f"{filename}.txt")

    with open(file_path, "w", encoding='utf-8') as file:
        file.write(transcript)

    return file_path

def get_playlist_videos(playlist_url):
    try:
        playlist = Playlist(playlist_url)
        return playlist.video_urls
    except Exception as e:
        st.error(f"Failed to fetch playlist videos: {str(e)}")
        return []

# Main Streamlit app
def main():
    st.title("YouTube Transcript Downloader")

    config = load_config()

    # Sidebar for settings
    st.sidebar.title("Settings")
    config['download_folder'] = st.sidebar.text_input("Download Folder", value=config['download_folder'])

    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["Single Video", "Channel/Playlist", "File Converter", "About"])

    with tab1:
        st.header("Single Video Transcript")
        video_url = st.text_input("Enter YouTube Video URL:")
        if st.button("Download Transcript"):
            if video_url:
                with st.spinner("Downloading transcript..."):
                    transcript = fetch_transcript(video_url)
                    if transcript:
                        filename = get_video_title(video_url)
                        save_path = save_transcript_to_text(transcript, filename, config['download_folder'])
                        if save_path:
                            st.success(f"Transcript saved to {save_path}")
                        else:
                            st.error("Failed to save the transcript.")
                    else:
                        st.error("Failed to fetch transcript.")
            else:
                st.warning("Please enter a valid YouTube URL.")

    with tab2:
        st.header("Channel/Playlist Transcripts")
        url_type = st.radio("Select URL type:", ("Channel", "Playlist"))
        url = st.text_input(f"Enter YouTube {url_type} URL:")
        if st.button("Download All Transcripts"):
            if url:
                with st.spinner(f"Downloading transcripts from {url_type}..."):
                    if url_type == "Playlist":
                        video_urls = get_playlist_videos(url)
                    else:  # Channel
                        st.error("Channel functionality not implemented in this version.")
                        video_urls = []

                    if video_urls:
                        progress_bar = st.progress(0)
                        for i, video_url in enumerate(video_urls):
                            transcript = fetch_transcript(video_url)
                            if transcript:
                                filename = get_video_title(video_url)
                                save_transcript_to_text(transcript, filename, config['download_folder'])
                            progress_bar.progress((i + 1) / len(video_urls))
                        st.success(f"All available transcripts downloaded to {config['download_folder']}")
                    else:
                        st.warning("No videos found or unable to process the URL.")
            else:
                st.warning(f"Please enter a valid YouTube {url_type} URL.")

    with tab3:
        st.header("File Converter")
        file_type = st.radio("Select file type to convert:", ("PDF", "DOCX"))
        uploaded_file = st.file_uploader(f"Choose a {file_type} file", type=[file_type.lower()])
        if uploaded_file is not None:
            if st.button("Convert to Text"):
                with st.spinner("Converting file..."):
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
                    else:
                        st.error("Failed to convert and save the file.")

    with tab4:
        st.header("About")
        st.write("""
        This application allows you to download transcripts from YouTube videos, playlists, and channels.
        It also provides functionality to convert PDF and DOCX files to plain text.

        Created by: Your Name
        Version: 1.0
        """)

    # Save config at the end
    save_config(config)

if __name__ == "__main__":
    main()