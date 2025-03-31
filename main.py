# course_video_tools/main.py

import tkinter
from tkinterdnd2 import Tk
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append("./")
sys.path.insert(0, SCRIPT_DIR)


from gui.main_app import MainApp  # Absolute import


if __name__ == "__main__":
    try:
        root = MainApp()
        root.mainloop()
    except tkinter.TclError as e:
        print(f"Error initializing Tkinter: {e}")
        print("Please ensure that Tkinter is properly installed and configured.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

