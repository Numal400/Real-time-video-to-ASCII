# Colored ASCII Video Player

A Windows terminal project that converts video frames into real-time colored ASCII art using:

- Python
- FFmpeg
- FFplay
- NumPy
- ANSI 24-bit True Color

## 1. Install Python

Install Python 3.11+ and make sure this works:

```powershell
python --version
```

## 2. Install FFmpeg

You need these commands available in PATH:

```powershell
ffmpeg -version
ffplay -version
ffprobe -version
```

All three normally come with an FFmpeg installation.

## 3. Create a virtual environment

Open this folder in VS Code and run:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Install the Python dependency:

```powershell
pip install -r requirements.txt
```

## 4. Add your video

Put your video inside:

```text
assets/
```

For example:

```text
assets/video.mp4
```

## 5. Run

```powershell
python main.py "assets\video.mp4"
```

Or use:

```powershell
run.bat
```

## Useful commands

Higher resolution:

```powershell
python main.py "assets\video.mp4" --width 140
```

Lower resolution / faster:

```powershell
python main.py "assets\video.mp4" --width 70
```

Disable audio:

```powershell
python main.py "assets\video.mp4" --no-audio
```

Change brightness:

```powershell
python main.py "assets\video.mp4" --brightness 1.2
```

Change contrast:

```powershell
python main.py "assets\video.mp4" --contrast 1.3
```

Use a different character set:

```powershell
python main.py "assets\video.mp4" --chars " .,:;irsXA253hMHGS#9B&@"
```

## Recommended terminal

Use Windows Terminal rather than the old Command Prompt.

For a good first test, maximize the terminal window and use:

```powershell
python main.py "assets\video.mp4" --width 100
```

## How it works

```text
Video
  |
  v
FFmpeg
  |
  | RGB24 raw frames
  v
Python / NumPy
  |
  +--> brightness calculation
  |
  +--> ASCII character mapping
  |
  +--> RGB color preservation
  |
  v
ANSI True Color terminal

Video
  |
  v
FFplay
  |
  v
Audio
```

Python controls the visual frame timing while FFplay handles the audio.

## Important

This is a terminal renderer, not a normal GUI video player. Rendering thousands of ANSI color escape sequences every frame is CPU-intensive.

If playback is slow, reduce the width:

```powershell
python main.py "assets\video.mp4" --width 60
```
