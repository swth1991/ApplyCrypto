import os
import re
import json
import sys
from pathlib import Path

# Add src to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent / 'src'
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from parser.digital_channel_parser import DigitalChannelParser


# FROM_SAMPLE_DIR = "examples"
FROM_SAMPLE_DIR = None

CONFIG_FILE = "config.json"
OUTPUT_FILE = "digital_chananel_specific_map.json"

def get_target_project():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("target_project")
    except Exception as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        return None

def find_java_files(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith("Dao.java") or file.endswith("DaoModel.java") or file.endswith("Service.java"):
                yield os.path.join(root, file)

def extract_info(file_path):
    parser = DigitalChannelParser()
    return parser.extract_info(file_path)

def main():
    if FROM_SAMPLE_DIR:
        print(f"Running in SAMPLE mode with directory: {FROM_SAMPLE_DIR}")
        target_dir = os.path.abspath(FROM_SAMPLE_DIR)
        file_list = find_java_files(target_dir)
    else:
        target_dir = get_target_project()
        if not target_dir:
            print("Could not find target_project in config.json")
            return

        print(f"Scanning target directory: {target_dir}")
        file_list = find_java_files(target_dir)
    
    result = {}
    
    count = 0
    for file_path in file_list:
        # print(f"Checking {file_path}...")
        namespace, class_name, methods = extract_info(file_path)
        if namespace:
            if namespace not in result:
                result[namespace] = {}
            
            result[namespace][class_name] = methods
            count += 1
            print(f"[{count}] Found {class_name} in {namespace} with {len(methods)} methods")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"Saved {count} entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
