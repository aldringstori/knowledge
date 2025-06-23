import streamlit as st
import pandas as pd
import os
from utils.logging_setup import logger
from utils.common import (
    create_folder,
    sanitize_filename,
    save_transcript_to_text,
    get_video_id_from_url,
    fetch_transcript
)
from youtube_transcript_api import YouTubeTranscriptApi


def process_item(item_data, folder_name, item_type='video', config=None):
    """
    Process a single video/short/playlist item and return status information

    Args:
        item_data (dict): Dictionary containing item information
        folder_name (str): Folder path to save transcript
        item_type (str): Type of item ('video', 'short', or 'playlist')
        config (dict): Configuration dictionary with settings like headless_mode

    Returns:
        tuple: (success, message, filename, url_fetched, video_downloaded)
    """
    try:
        url = item_data['url']
        title = item_data['title']
        url_fetched = True  # URL was successfully fetched to get here
        video_downloaded = False

        if item_type == 'short':
            url = url.replace("/shorts/", "/watch?v=")
            video_id = get_video_id_from_url(url)
            if not video_id:
                return False, "Invalid video ID", None, url_fetched, video_downloaded

            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = transcript_list.find_transcript(['en']).fetch()
                text = ' '.join([entry['text'] for entry in transcript])
                video_downloaded = True
            except Exception as e:
                return False, str(e), None, url_fetched, video_downloaded
        else:
            # Get headless mode from config
            headless_mode = config.get('headless_mode', False) if config else False
            text = fetch_transcript(url, headless=headless_mode)
            if not text:
                return False, "No transcript available", None, url_fetched, video_downloaded
            video_downloaded = True

        save_path = save_transcript_to_text(
            text,
            title,
            folder_name
        )

        if save_path:
            filename = os.path.basename(save_path)
            return True, "Success", filename, url_fetched, video_downloaded
        return False, "Failed to save transcript", None, url_fetched, video_downloaded

    except Exception as e:
        error_msg = f"Error processing {title}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None, True, False


def create_data_table():
    """Create an empty DataFrame with the required columns"""
    return pd.DataFrame(columns=['Title', 'URL Fetched', 'Video Downloaded', 'Status', 'Message', 'Saved File'])


def update_table_state(table_data):
    """Update the table in Streamlit's session state"""
    if 'status_table' not in st.session_state:
        st.session_state.status_table = create_data_table()

    st.session_state.status_table = pd.concat([
        st.session_state.status_table,
        pd.DataFrame([table_data])
    ]).reset_index(drop=True)


def display_table():
    """Display the current state of the table"""
    if 'status_table' in st.session_state:
        st.dataframe(
            st.session_state.status_table,
            column_config={
                "Title": st.column_config.TextColumn(
                    "Title",
                    width="medium",
                    help="Item title"
                ),
                "URL Fetched": st.column_config.TextColumn(
                    "URL Fetched",
                    width="small",
                    help="Whether the video URL was successfully fetched"
                ),
                "Video Downloaded": st.column_config.TextColumn(
                    "Video Downloaded",
                    width="small",
                    help="Whether the video transcript was successfully downloaded"
                ),
                "Status": st.column_config.TextColumn(
                    "Status",
                    width="small"
                ),
                "Message": st.column_config.TextColumn(
                    "Message",
                    width="medium"
                ),
                "Saved File": st.column_config.TextColumn(
                    "Saved File",
                    width="medium"
                )
            },
            hide_index=False
        )


def process_items_with_progress(items, folder_name, item_type='video', config=None):
    """
    Process a list of items with progress tracking and table display

    Args:
        items (list): List of items to process
        folder_name (str): Folder path to save transcripts
        item_type (str): Type of items ('video', 'short', or 'playlist')
        config (dict): Configuration dictionary with settings like headless_mode

    Returns:
        list: List of status dictionaries
    """
    # Create progress bar and table placeholder
    progress_bar = st.progress(0)
    table_container = st.empty()

    # Reset the table state for new batch
    st.session_state.status_table = create_data_table()

    for i, item in enumerate(items):
        success, message, filename, url_fetched, video_downloaded = process_item(item, folder_name, item_type, config)

        # Update table state
        update_table_state({
            'Title': item['title'],
            'URL Fetched': '✅' if url_fetched else '❌',
            'Video Downloaded': '✅' if video_downloaded else '❌',
            'Status': '✅' if success else '❌',
            'Message': message,
            'Saved File': filename if filename else 'N/A'
        })

        # Update progress
        progress_bar.progress((i + 1) / len(items))

        # Display updated table
        with table_container:
            display_table()

    return st.session_state.status_table.to_dict('records')


def save_report(status_data, folder_name, prefix):
    """
    Save status report to CSV

    Args:
        status_data (list): List of status dictionaries
        folder_name (str): Folder path to save report
        prefix (str): Prefix for report filename
    """
    if st.button("Download Summary Report"):
        df = pd.DataFrame(status_data)
        report_path = os.path.join(folder_name, f"{prefix}_report.csv")
        df.to_csv(report_path, index=False)
        st.success(f"Summary report saved to {report_path}")


def render_with_progress(
        fetch_function,
        url: str,
        config: dict,
        item_type='video',
        name_suffix=""
):
    """
    Main render function for processing items with progress tracking

    Args:
        fetch_function (callable): Function to fetch items from URL
        url (str): URL to process
        config (dict): Configuration dictionary
        item_type (str): Type of items ('video', 'short', or 'playlist')
        name_suffix (str): Suffix to add to folder name

    Returns:
        bool: Success status
    """
    try:
        name_extractor = config.get('name_extractor', lambda x: os.path.basename(x))
        name = name_extractor(url)
        folder_name = os.path.join(config['download_folder'], f"{name}{name_suffix}")
        create_folder(folder_name)

        items = fetch_function(url)
        if not items:
            st.error(f"No {item_type}s found")
            return False

        st.info(f"Found {len(items)} {item_type}s")

        status_data = process_items_with_progress(items, folder_name, item_type, config)

        successful = sum(1 for s in status_data if s['Status'] == '✅')
        st.success(f"Downloaded {successful} out of {len(items)} transcripts to {folder_name}")

        save_report(status_data, folder_name, name)
        return True

    except Exception as e:
        logger.error(f"Error processing {item_type}s: {str(e)}")
        st.error(f"Error processing {item_type}s: {str(e)}")
        return False