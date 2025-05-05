# test_prompt_files.py

"""
Simple test to verify prompt files exist and can be read.
"""

import os

def read_file(file_path):
    """Read a file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"✅ Successfully read {file_path} ({len(content)} chars)")
            return content
    except Exception as e:
        print(f"❌ Failed to read {file_path}: {str(e)}")
        return None

def main():
    """Test reading each prompt file."""
    prompt_files = [
        "gpt/prompts/filter_prompt.txt",
        "gpt/prompts/insight_prompt.txt",
        "gpt/prompts/community_discovery.txt"
    ]

    success = True
    for file_path in prompt_files:
        content = read_file(file_path)
        if not content:
            success = False

    return success

if __name__ == "__main__":
    print("Testing prompt file reading...")
    if main():
        print("\nAll prompt files read successfully!")
    else:
        print("\nOne or more prompt files could not be read")