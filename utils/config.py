import json
import os

def get_config():
    """Load configuration from settings.json"""
    settings_path = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
    try:
        with open(settings_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        raise Exception("settings.json not found. Please ensure it exists in the project root.")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON in settings.json. Please check the file syntax.")
    except Exception as e:
        raise Exception(f"Error loading config: {str(e)}")

def save_config(config):
    """Save configuration to settings.json"""
    settings_path = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
    with open(settings_path, 'w') as f:
        json.dump(config, f, indent=4)

def update_config(key, value):
    """Update a specific key in the config"""
    config = get_config()
    config[key] = value
    save_config(config)

def delete_files():
    """Placeholder for delete_files function"""
    return True, "Files deleted successfully"


def get_transcript_files():
    """Placeholder for get_transcript_files function"""
    config = get_config()
    folder = config.get('download_folder', '')
    if not os.path.exists(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.txt')]