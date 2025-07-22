import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from utils.logging_setup import get_module_logger

logger = get_module_logger("channel_manager")

class ChannelManager:
    """Manages YouTube channel tracking and video download history"""
    
    def __init__(self, channels_file: str = "data/channels.json"):
        self.channels_file = channels_file
        self.ensure_data_directory()
        self.channels_data = self.load_channels()
    
    def ensure_data_directory(self):
        """Ensure data directory exists"""
        data_dir = os.path.dirname(self.channels_file)
        if data_dir and not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
            except PermissionError:
                # If we can't create the data directory, use a fallback location
                logger.warning(f"Cannot create data directory {data_dir}, using fallback location")
                # Use a writable location like /tmp or current directory
                fallback_dir = "/tmp/knowledge_data"
                os.makedirs(fallback_dir, exist_ok=True)
                # Update the channels file path to use the fallback location
                filename = os.path.basename(self.channels_file)
                self.channels_file = os.path.join(fallback_dir, filename)
                logger.info(f"Using fallback channels file: {self.channels_file}")
    
    def load_channels(self) -> Dict:
        """Load channels data from JSON file"""
        if not os.path.exists(self.channels_file):
            return {"channels": {}, "metadata": {"created": datetime.now().isoformat(), "version": "1.0"}}
        
        try:
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure structure exists
                if "channels" not in data:
                    data["channels"] = {}
                if "metadata" not in data:
                    data["metadata"] = {"created": datetime.now().isoformat(), "version": "1.0"}
                return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading channels file: {e}")
            return {"channels": {}, "metadata": {"created": datetime.now().isoformat(), "version": "1.0"}}
    
    def save_channels(self):
        """Save channels data to JSON file"""
        try:
            self.channels_data["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump(self.channels_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Channels data saved to {self.channels_file}")
        except Exception as e:
            logger.error(f"Error saving channels file: {e}")
    
    def add_channel(self, channel_url: str, channel_name: str, description: str = "") -> bool:
        """Add a new channel to tracking"""
        try:
            channel_id = self.extract_channel_id(channel_url)
            if not channel_id:
                logger.error(f"Invalid channel URL: {channel_url}")
                return False
            
            if channel_id in self.channels_data["channels"]:
                logger.warning(f"Channel {channel_name} already exists")
                return False
            
            self.channels_data["channels"][channel_id] = {
                "name": channel_name,
                "url": channel_url,
                "description": description,
                "added_date": datetime.now().isoformat(),
                "last_checked": None,
                "video_count": 0,
                "downloaded_videos": {},
                "status": "active"
            }
            
            self.save_channels()
            logger.info(f"Added channel: {channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False
    
    def remove_channel(self, channel_id: str) -> bool:
        """Remove a channel from tracking"""
        try:
            if channel_id not in self.channels_data["channels"]:
                logger.warning(f"Channel ID {channel_id} not found")
                return False
            
            channel_name = self.channels_data["channels"][channel_id]["name"]
            del self.channels_data["channels"][channel_id]
            self.save_channels()
            logger.info(f"Removed channel: {channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing channel: {e}")
            return False
    
    def update_channel(self, channel_id: str, **kwargs) -> bool:
        """Update channel information"""
        try:
            if channel_id not in self.channels_data["channels"]:
                logger.warning(f"Channel ID {channel_id} not found")
                return False
            
            for key, value in kwargs.items():
                if key in ["name", "url", "description", "status"]:
                    self.channels_data["channels"][channel_id][key] = value
            
            self.save_channels()
            logger.info(f"Updated channel: {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating channel: {e}")
            return False
    
    def add_downloaded_video(self, channel_id: str, video_url: str, video_title: str, 
                           transcript_path: str = None) -> bool:
        """Track a downloaded video for a channel"""
        try:
            if channel_id not in self.channels_data["channels"]:
                logger.warning(f"Channel ID {channel_id} not found")
                return False
            
            video_id = self.extract_video_id(video_url)
            if not video_id:
                logger.error(f"Invalid video URL: {video_url}")
                return False
            
            self.channels_data["channels"][channel_id]["downloaded_videos"][video_id] = {
                "title": video_title,
                "url": video_url,
                "download_date": datetime.now().isoformat(),
                "transcript_path": transcript_path,
                "status": "completed"
            }
            
            # Update video count
            self.channels_data["channels"][channel_id]["video_count"] = len(
                self.channels_data["channels"][channel_id]["downloaded_videos"]
            )
            self.channels_data["channels"][channel_id]["last_checked"] = datetime.now().isoformat()
            
            self.save_channels()
            logger.info(f"Added downloaded video: {video_title}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding downloaded video: {e}")
            return False
    
    def get_channels_list(self) -> List[Dict]:
        """Get list of all channels for display"""
        channels_list = []
        for channel_id, data in self.channels_data["channels"].items():
            channels_list.append({
                "channel_id": channel_id,
                "name": data["name"],
                "url": data["url"],
                "description": data.get("description", ""),
                "added_date": data["added_date"],
                "last_checked": data.get("last_checked", "Never"),
                "video_count": data.get("video_count", 0),
                "status": data.get("status", "active")
            })
        return sorted(channels_list, key=lambda x: x["added_date"], reverse=True)
    
    def get_channel_videos(self, channel_id: str) -> List[Dict]:
        """Get list of downloaded videos for a channel"""
        if channel_id not in self.channels_data["channels"]:
            return []
        
        videos = []
        downloaded_videos = self.channels_data["channels"][channel_id].get("downloaded_videos", {})
        for video_id, data in downloaded_videos.items():
            videos.append({
                "video_id": video_id,
                "title": data["title"],
                "url": data["url"],
                "download_date": data["download_date"],
                "transcript_path": data.get("transcript_path"),
                "status": data.get("status", "completed")
            })
        return sorted(videos, key=lambda x: x["download_date"], reverse=True)
    
    def is_video_downloaded(self, channel_id: str, video_url: str) -> bool:
        """Check if a video is already downloaded for a channel"""
        if channel_id not in self.channels_data["channels"]:
            return False
        
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return False
        
        return video_id in self.channels_data["channels"][channel_id].get("downloaded_videos", {})
    
    def get_channel_stats(self) -> Dict:
        """Get overall statistics"""
        total_channels = len(self.channels_data["channels"])
        total_videos = sum(
            len(channel.get("downloaded_videos", {})) 
            for channel in self.channels_data["channels"].values()
        )
        active_channels = sum(
            1 for channel in self.channels_data["channels"].values()
            if channel.get("status", "active") == "active"
        )
        
        return {
            "total_channels": total_channels,
            "active_channels": active_channels,
            "total_videos": total_videos,
            "last_updated": self.channels_data["metadata"].get("last_updated", "Never")
        }
    
    @staticmethod
    def extract_channel_id(url: str) -> Optional[str]:
        """Extract channel ID from YouTube URL"""
        try:
            if "@" in url:
                # Handle @username format
                return url.split("@")[-1].split("/")[0]
            elif "/channel/" in url:
                # Handle /channel/UC... format
                return url.split("/channel/")[-1].split("/")[0]
            elif "/c/" in url:
                # Handle /c/channelname format
                return url.split("/c/")[-1].split("/")[0]
            elif "/user/" in url:
                # Handle /user/username format
                return url.split("/user/")[-1].split("/")[0]
            else:
                # Try to extract from various formats
                return url.split("/")[-1] if "/" in url else url
        except Exception:
            return None
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        try:
            if "watch?v=" in url:
                return url.split("watch?v=")[-1].split("&")[0]
            elif "shorts/" in url:
                return url.split("shorts/")[-1].split("?")[0]
            elif "youtu.be/" in url:
                return url.split("youtu.be/")[-1].split("?")[0]
            return None
        except Exception:
            return None
    
    def find_channel_for_video(self, video_url: str) -> Optional[str]:
        """Find which tracked channel a video belongs to (if any)"""
        try:
            # This is a simplified implementation
            # In a real scenario, you'd need to fetch the video's channel information
            # from YouTube API or scrape the video page
            
            # For now, we'll use a basic pattern matching approach
            # This can be enhanced later with proper YouTube API integration
            
            # Extract video ID
            video_id = self.extract_video_id(video_url)
            if not video_id:
                return None
            
            # Check if video is already tracked under any channel
            for channel_id, channel_data in self.channels_data["channels"].items():
                if video_id in channel_data.get("downloaded_videos", {}):
                    return channel_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding channel for video: {e}")
            return None
    
    def track_video_download(self, video_url: str, video_title: str, transcript_path: str = None) -> bool:
        """Automatically track a video download if it belongs to a monitored channel"""
        try:
            channel_id = self.find_channel_for_video(video_url)
            if channel_id:
                return self.add_downloaded_video(channel_id, video_url, video_title, transcript_path)
            return False
        except Exception as e:
            logger.error(f"Error tracking video download: {e}")
            return False