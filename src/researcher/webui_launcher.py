"""
Launcher for Streamlit WebUI.

This module provides a wrapper entry point that properly launches the Streamlit
WebUI application using subprocess, ensuring correct runtime environment setup.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch Streamlit WebUI application.
    
    This function uses subprocess.run to invoke the Streamlit runtime with
    the WebUI module, ensuring proper environment setup and signal handling.
    """
    webui_path = Path(__file__).parent / "Home.py"
    
    try:
        # Run streamlit with the WebUI module
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(webui_path)],
            check=False
        )
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n[INFO] Streamlit WebUI を終了しました")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] WebUI起動エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
