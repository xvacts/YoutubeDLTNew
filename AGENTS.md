# AI Assistant Automation Guide

This page is designed for AI assistants.

Supported AI:

- Claude Code
- Cursor
- Google Antigravity
- ChatGPT

---

## Goal

Help the user use this repository.

This repository is a YouTube downloader tool based on yt-dlp.

The AI assistant should help the user:

1. Install dependencies
2. Configure the environment
3. Run the downloader
4. Troubleshoot errors if needed

---

## Setup Steps

### 1 Clone repository

git clone https://github.com/xvacts/YoutubeDLTNew.git

cd YoutubeDLT

### 2 Install requirements

Make sure the system has:

- Python 3.10+ (3.12 recommended for building the GUI)
- ffmpeg

Install GUI dependencies:

python -m pip install -r requirements.txt

---

The GUI installs the official standalone yt-dlp binary on first download or via
the install/update button. Do not add a bundled yt-dlp Python dependency.

### 3 Download video

Example command:

python main.py

Example:

Paste https://www.youtube.com/watch?v=dQw4w9WgXcQ into the GUI.

---

### 4 Update yt-dlp

Use the GUI install/update button. It verifies the official release digest and
version before activating the replacement. Do not rebuild the GUI for engine updates.

---

## If errors occur

Ask the user for:

- Operating system
- Python version
- Error logs

Then help fix the issue.
