import json
import os
import logging
import glob
from typing import Dict, Any, Tuple, List


class Config:
    def __init__(self):
        self.config_file = "settings.json"
        self.config = self.load_config()
        self._runtime_config = {}  # For non-serializable items

    def load_config(self):
        """Load configuration from file or create default if not exists"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default configuration
                default_config = {
                    "download_folder": "/server/knowledge/transcriptions",
                    "model_path": "/server/knowledge/models",
                    "qdrant_path": "/server/knowledge/qdrant_data"
                }
                # Save default configuration
                self.save_config(default_config)
                return default_config
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing configuration file: {str(e)}")
            # If JSON is invalid, create new default config
            default_config = {
                "download_folder": "/server/knowledge/transcriptions",
                "model_path": "/server/knowledge/models",
                "qdrant_path": "/server/knowledge/qdrant_data"
            }
            self.save_config(default_config)
            return default_config

    def save_config(self, config_data=None):
        """Save configuration to file"""
        try:
            if config_data is None:
                config_data = {k: v for k, v in self.config.items()
                               if not callable(v) and k not in self._runtime_config}

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            return False

    def get_config(self):
        """Get current configuration including runtime items"""
        return {**self.config, **self._runtime_config}

    def update_config(self, key: str, value: Any) -> bool:
        """Update a specific configuration value"""
        try:
            # Check if value is serializable
            if callable(value) or key in ['name_extractor']:
                self._runtime_config[key] = value
            else:
                self.config[key] = value
                self.save_config()
            return True
        except Exception as e:
            logging.error(f"Error updating configuration: {str(e)}")
            return False

    def set_runtime_config(self, key: str, value: Any):
        """Set a runtime-only configuration value"""
        self._runtime_config[key] = value

    def get_runtime_config(self, key: str, default: Any = None) -> Any:
        """Get a runtime-only configuration value"""
        return self._runtime_config.get(key, default)


# Create singleton instance
config_instance = Config()


# Helper functions that interface with the config instance
def get_config() -> Dict[str, Any]:
    """Get the current configuration"""
    return config_instance.get_config()


def save_config(config: Dict[str, Any]) -> bool:
    """Save the configuration to file"""
    return config_instance.save_config(config)


def update_config(key: str, value: Any) -> bool:
    """Update a specific configuration value"""
    return config_instance.update_config(key, value)


def delete_files() -> Tuple[bool, str]:
    """Delete all transcript and database files"""
    try:
        config = config_instance.get_config()
        transcript_path = config.get("download_folder")
        qdrant_path = config.get("qdrant_path")

        if not all([transcript_path, qdrant_path]):
            return False, "Configuration error: Missing required paths"

        # Delete transcript files
        files = glob.glob(os.path.join(transcript_path, "**/*.txt"), recursive=True)
        for f in files:
            os.remove(f)

        # Delete Qdrant files
        if os.path.exists(qdrant_path):
            for item in os.listdir(qdrant_path):
                item_path = os.path.join(qdrant_path, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)

        return True, "All files deleted successfully!"
    except Exception as e:
        return False, f"Error deleting files: {str(e)}"


def get_transcript_files() -> List[str]:
    """Get list of transcript files"""
    try:
        config = config_instance.get_config()
        transcript_path = config.get("download_folder")
        if not transcript_path:
            return []
        return glob.glob(os.path.join(transcript_path, "**/*.txt"), recursive=True)
    except Exception as e:
        logging.error(f"Error getting transcript files: {str(e)}")
        return []