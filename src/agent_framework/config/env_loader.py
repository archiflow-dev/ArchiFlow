import os

def load_env(file_path: str = ".env") -> None:
    """
    Load environment variables from a .env file.
    
    Args:
        file_path: Path to the .env file. Defaults to ".env" in the current directory.
    """
    if not os.path.exists(file_path):
        # Try looking in parent directories if not found in current
        # This is helpful when running from subdirectories or tests
        current_dir = os.getcwd()
        parent_path = os.path.join(os.path.dirname(current_dir), file_path)
        if os.path.exists(parent_path):
            file_path = parent_path
        else:
            # If still not found, just return silently (optional config)
            return

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # Set env var if not already set (allow shell override)
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        print(f"Warning: Failed to load .env file: {e}")
