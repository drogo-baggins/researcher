"""
Backward compatibility wrapper for webui.py.

This file redirects to the new multipage structure (Home.py).
For new installations, please use Home.py directly.

Legacy users can continue to run this file, but it will show a deprecation warning.
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run Home.py
from Home import main

if __name__ == "__main__":
    st.warning("⚠️ webui.pyは非推奨です。今後はHome.pyを使用してください。")
    main()
