
import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "max_retries": 3,
    "backoff_base": 2  
}

def get_config():
    """
    Loads configuration from config.json.
    Creates the file with defaults if it doesn't exist.
    """
    if not os.path.exists(CONFIG_FILE):
        print(f"Creating default config file: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {CONFIG_FILE}. Using defaults.")
        return DEFAULT_CONFIG

