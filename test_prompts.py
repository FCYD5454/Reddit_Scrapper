# test_prompts.py

"""
Test script to verify that all prompt templates are loading correctly.
"""

import os
import sys
from gpt.filters import load_filter_prompt_template
from gpt.insights import load_insight_prompt_template
from reddit.discovery import load_discovery_prompt_template
from utils.logger import setup_logger

log = setup_logger()

def test_prompt_loading():
    """Test that all prompts can be loaded from their files."""
    success = True

    # Test filter prompt
    filter_prompt = load_filter_prompt_template()
    if not filter_prompt or len(filter_prompt) < 10:
        log.error("Failed to load filter prompt or prompt is too short")
        success = False
    else:
        log.info(f"✅ Filter prompt loaded successfully ({len(filter_prompt)} chars)")

    # Test insight prompt
    insight_prompt = load_insight_prompt_template()
    if not insight_prompt or len(insight_prompt) < 10:
        log.error("Failed to load insight prompt or prompt is too short")
        success = False
    else:
        log.info(f"✅ Insight prompt loaded successfully ({len(insight_prompt)} chars)")

    # Test discovery prompt
    discovery_prompt = load_discovery_prompt_template()
    if not discovery_prompt or len(discovery_prompt) < 10:
        log.error("Failed to load discovery prompt or prompt is too short")
        success = False
    else:
        log.info(f"✅ Community discovery prompt loaded successfully ({len(discovery_prompt)} chars)")

    return success

if __name__ == "__main__":
    log.info("Testing prompt template loading...")
    success = test_prompt_loading()

    if success:
        log.info("All prompt templates loaded successfully!")
        sys.exit(0)
    else:
        log.error("One or more prompt templates failed to load")
        sys.exit(1)