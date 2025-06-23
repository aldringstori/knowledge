import streamlit as st
import pandas as pd
from datetime import datetime
from utils.channel_manager import ChannelManager
from utils.logging_setup import setup_logger

logger = setup_logger(__name__)

def render_channel_manager():
    """Render the channel management interface"""
    st.title("📺 Channel Manager")
    
    # Initialize channel manager
    if 'channel_manager' not in st.session_state:
        st.session_state.channel_manager = ChannelManager()
    
    cm = st.session_state.channel_manager
    
    # Display statistics
    stats = cm.get_channel_stats()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Channels", stats["total_channels"])
    with col2:
        st.metric("Active Channels", stats["active_channels"])
    with col3:
        st.metric("Total Videos", stats["total_videos"])
    with col4:
        st.metric("Last Updated", stats["last_updated"][:10] if stats["last_updated"] != "Never" else "Never")
    
    # Tabs for different operations
    tab1, tab2, tab3 = st.tabs(["📋 Channel List", "➕ Add Channel", "📊 Channel Details"])
    
    with tab1:
        render_channels_table(cm)
    
    with tab2:
        render_add_channel_form(cm)
    
    with tab3:
        render_channel_details(cm)

def render_channels_table(cm: ChannelManager):
    """Render the channels table with management options"""
    st.subheader("Saved Channels")
    
    channels = cm.get_channels_list()
    
    if not channels:
        st.info("No channels saved yet. Add your first channel using the 'Add Channel' tab.")
        return
    
    # Convert to DataFrame for better display
    df_channels = pd.DataFrame(channels)
    
    # Format dates for display
    if not df_channels.empty:
        df_channels['added_date'] = pd.to_datetime(df_channels['added_date']).dt.strftime('%Y-%m-%d %H:%M')
        df_channels['last_checked'] = df_channels['last_checked'].apply(
            lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M') if x != "Never" and x else "Never"
        )
    
    # Display table with selection
    selected_rows = st.dataframe(
        df_channels[['name', 'description', 'video_count', 'added_date', 'last_checked', 'status']],
        column_config={
            "name": "Channel Name",
            "description": "Description", 
            "video_count": "Videos",
            "added_date": "Added",
            "last_checked": "Last Checked",
            "status": "Status"
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Channel management buttons
    if not df_channels.empty:
        st.subheader("Channel Management")
        
        # Select channel for operations
        channel_names = [f"{row['name']} ({row['channel_id']})" for _, row in df_channels.iterrows()]
        selected_channel = st.selectbox("Select Channel for Operations:", [""] + channel_names)
        
        if selected_channel:
            channel_id = selected_channel.split(" (")[-1].rstrip(")")
            channel_data = df_channels[df_channels['channel_id'] == channel_id].iloc[0]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Update Status", key=f"update_{channel_id}"):
                    new_status = "inactive" if channel_data['status'] == "active" else "active"
                    if cm.update_channel(channel_id, status=new_status):
                        st.success(f"Status updated to {new_status}")
                        st.rerun()
                    else:
                        st.error("Failed to update status")
            
            with col2:
                if st.button("✏️ Edit Info", key=f"edit_{channel_id}"):
                    st.session_state[f"editing_{channel_id}"] = True
            
            with col3:
                if st.button("🗑️ Remove", key=f"remove_{channel_id}"):
                    if st.session_state.get(f"confirm_remove_{channel_id}", False):
                        if cm.remove_channel(channel_id):
                            st.success("Channel removed successfully")
                            st.session_state[f"confirm_remove_{channel_id}"] = False
                            st.rerun()
                        else:
                            st.error("Failed to remove channel")
                    else:
                        st.session_state[f"confirm_remove_{channel_id}"] = True
                        st.warning("Click again to confirm removal")
            
            # Edit form
            if st.session_state.get(f"editing_{channel_id}", False):
                with st.form(f"edit_channel_{channel_id}"):
                    st.subheader(f"Edit Channel: {channel_data['name']}")
                    new_name = st.text_input("Channel Name", value=channel_data['name'])
                    new_description = st.text_area("Description", value=channel_data['description'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Save Changes"):
                            if cm.update_channel(channel_id, name=new_name, description=new_description):
                                st.success("Channel updated successfully")
                                st.session_state[f"editing_{channel_id}"] = False
                                st.rerun()
                            else:
                                st.error("Failed to update channel")
                    
                    with col2:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state[f"editing_{channel_id}"] = False
                            st.rerun()

def render_add_channel_form(cm: ChannelManager):
    """Render form to add new channels"""
    st.subheader("Add New Channel")
    
    with st.form("add_channel_form"):
        st.write("Add a YouTube channel to track downloaded videos.")
        
        channel_url = st.text_input(
            "Channel URL*",
            placeholder="https://youtube.com/@channelname or https://youtube.com/channel/UC...",
            help="Paste the full YouTube channel URL"
        )
        
        channel_name = st.text_input(
            "Channel Name*",
            placeholder="Enter a friendly name for this channel",
            help="This will be displayed in the channel list"
        )
        
        description = st.text_area(
            "Description (optional)",
            placeholder="Add notes about this channel...",
            help="Optional description or notes about the channel"
        )
        
        submitted = st.form_submit_button("➕ Add Channel")
        
        if submitted:
            if not channel_url or not channel_name:
                st.error("Please fill in both Channel URL and Channel Name")
            elif not any(domain in channel_url.lower() for domain in ['youtube.com', 'youtu.be']):
                st.error("Please enter a valid YouTube channel URL")
            else:
                if cm.add_channel(channel_url, channel_name, description):
                    st.success(f"✅ Channel '{channel_name}' added successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to add channel. It may already exist or the URL is invalid.")
    
    # Quick add section
    st.subheader("Quick Add Popular Channels")
    st.write("Click to quickly add popular educational/tech channels:")
    
    quick_channels = [
        ("https://youtube.com/@3Blue1Brown", "3Blue1Brown", "Mathematics and visualization"),
        ("https://youtube.com/@TechLead", "TechLead", "Programming and tech career"),
        ("https://youtube.com/@fireship", "Fireship", "Web development tutorials"),
        ("https://youtube.com/@TheNetNinja", "The Net Ninja", "Web development tutorials"),
    ]
    
    cols = st.columns(2)
    for i, (url, name, desc) in enumerate(quick_channels):
        with cols[i % 2]:
            if st.button(f"Add {name}", key=f"quick_add_{i}"):
                if cm.add_channel(url, name, desc):
                    st.success(f"Added {name}!")
                    st.rerun()
                else:
                    st.warning(f"{name} already exists or failed to add")

def render_channel_details(cm: ChannelManager):
    """Render detailed view of a specific channel"""
    st.subheader("Channel Details")
    
    channels = cm.get_channels_list()
    if not channels:
        st.info("No channels available. Add channels first.")
        return
    
    # Channel selection
    channel_options = {f"{ch['name']} ({ch['video_count']} videos)": ch['channel_id'] for ch in channels}
    selected_channel_name = st.selectbox("Select Channel:", [""] + list(channel_options.keys()))
    
    if not selected_channel_name:
        return
    
    channel_id = channel_options[selected_channel_name]
    channel_info = next(ch for ch in channels if ch['channel_id'] == channel_id)
    
    # Display channel info
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Channel Name", channel_info['name'])
        st.metric("Total Videos", channel_info['video_count'])
        st.metric("Status", channel_info['status'].title())
    
    with col2:
        st.metric("Added Date", channel_info['added_date'][:10])
        st.metric("Last Checked", channel_info['last_checked'][:10] if channel_info['last_checked'] != "Never" else "Never")
        st.write(f"**URL:** [{channel_info['url']}]({channel_info['url']})")
    
    if channel_info['description']:
        st.write(f"**Description:** {channel_info['description']}")
    
    # Display downloaded videos
    st.subheader("Downloaded Videos")
    videos = cm.get_channel_videos(channel_id)
    
    if not videos:
        st.info("No videos downloaded from this channel yet.")
    else:
        # Convert to DataFrame
        df_videos = pd.DataFrame(videos)
        df_videos['download_date'] = pd.to_datetime(df_videos['download_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Display videos table
        st.dataframe(
            df_videos[['title', 'download_date', 'status']],
            column_config={
                "title": "Video Title",
                "download_date": "Downloaded",
                "status": "Status"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Export options
        st.subheader("Export Options")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export Video List (CSV)"):
                csv_data = df_videos.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"{channel_info['name']}_videos.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📋 Copy URLs"):
                urls = "\n".join(df_videos['url'].tolist())
                st.code(urls, language="text")
                st.info("URLs displayed above - copy manually")

def render_url(url: str, config: dict):
    """Interface for the main app routing"""
    render_channel_manager()