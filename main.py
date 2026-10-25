"""Application entry point; launch with ``python main.py``."""

import tkinter as tk

from app.ui.main_window import AudioPlaylistDownloader


def main() -> None:
    """Create the Tk window and start its event loop."""
    root = tk.Tk()
    AudioPlaylistDownloader(root)
    root.mainloop()


if __name__ == "__main__":
    main()
