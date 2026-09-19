import json
import subprocess
import sys

import numpy as np


# ============================================================
# DENSE CHARACTER SET
# ============================================================
# Dark → bright
# More characters = smoother brightness transitions
# ============================================================

CHARSET = (
    " .'`^\",:;Il!i~+_-?][}{1)(|\\/"
    "tfjrxnuvczXYUJCLQ0OZmwqpdbkhao"
    "*#MW&8%B@$"
)


def get_video_info(video_path):
    """
    Get video width, height and FPS using FFprobe.
    """

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-of",
        "json",
        video_path,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    stream = data["streams"][0]

    width = int(stream["width"])
    height = int(stream["height"])

    fps_text = stream["r_frame_rate"]

    if "/" in fps_text:
        numerator, denominator = fps_text.split("/")
        fps = float(numerator) / float(denominator)
    else:
        fps = float(fps_text)

    return {
        "width": width,
        "height": height,
        "fps": fps,
    }


def build_ffmpeg_command(video_path, width, height, fps):
    """
    Creates the FFmpeg command used to stream raw RGB frames.
    """

    filter_string = (
        f"fps={fps:.6f},"
        f"scale={width}:{height}:flags=lanczos"
    )

    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",

        "-i",
        video_path,

        "-an",

        "-vf",
        filter_string,

        "-f",
        "rawvideo",

        "-pix_fmt",
        "rgb24",

        "pipe:1",
    ]


def start_audio(video_path):
    """
    Play the original video's audio through FFplay.
    """

    return subprocess.Popen(
        [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-vn",
            video_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class VideoASCIIRenderer:

    def __init__(
        self,
        width=100,
        chars=CHARSET,
        brightness=1.05,
        contrast=1.20,
    ):
        self.target_width = max(20, int(width))

        self.chars = chars

        self.brightness = float(brightness)

        self.contrast = float(contrast)

    # ========================================================
    # CALCULATE TERMINAL SIZE
    # ========================================================

    def calculate_size(self, video_width, video_height):

        width = self.target_width

        
        aspect_ratio = video_height / max(video_width, 1)

        height = int(
            width
            * aspect_ratio
            * 0.50
        )

        height = max(2, height)

        return width, height

    # ========================================================
    # BRIGHTNESS / CONTRAST
    # ========================================================

    def adjust_image(self, frame):

        frame = frame.astype(np.float32)

        # ----------------------------------------------------
        # CONTRAST
        # ----------------------------------------------------

        frame = (
            (frame - 127.5)
            * self.contrast
            + 127.5
        )

        # ----------------------------------------------------
        # BRIGHTNESS
        # ----------------------------------------------------

        frame *= self.brightness

        frame = np.clip(
            frame,
            0,
            255,
        )

        return frame.astype(np.uint8)

    # ========================================================
    # DITHERING
    # ========================================================

    def apply_dither(self, brightness):

        """
        Small ordered dithering pattern.

        This prevents large flat areas from looking too
        banded when converting brightness into characters.
        """

        pattern = np.array(
            [
                [0, 2],
                [3, 1],
            ],
            dtype=np.float32,
        )

        pattern = (
            pattern / 4.0 - 0.5
        ) * 12.0

        h, w = brightness.shape

        dither = np.tile(
            pattern,
            (
                h // 2 + 1,
                w // 2 + 1,
            ),
        )

        dither = dither[:h, :w]

        brightness = brightness + dither

        return np.clip(
            brightness,
            0,
            255,
        )

    # ========================================================
    # CONVERT BRIGHTNESS → CHARACTER
    # ========================================================

    def brightness_to_chars(self, brightness):

        """
        Convert grayscale brightness into characters.

        Black  → space
        White  → @
        """

        number_of_chars = len(self.chars)

        indexes = (
            brightness
            / 255.0
            * (number_of_chars - 1)
        )

        indexes = indexes.astype(
            np.int32
        )

        indexes = np.clip(
            indexes,
            0,
            number_of_chars - 1,
        )

        return indexes

    # ========================================================
    # RENDER FRAME
    # ========================================================

    def render(self, raw, width, height):

        # ----------------------------------------------------
        # Convert FFmpeg bytes → NumPy image
        # ----------------------------------------------------

        frame = np.frombuffer(
            raw,
            dtype=np.uint8,
        )

        expected_size = (
            width
            * height
            * 3
        )

        if frame.size < expected_size:
            return

        frame = frame[
            :expected_size
        ]

        frame = frame.reshape(
            (
                height,
                width,
                3,
            )
        )

        # ----------------------------------------------------
        # Brightness / contrast
        # ----------------------------------------------------

        frame = self.adjust_image(
            frame
        )

        # ----------------------------------------------------
        # Calculate perceived brightness
        #
        # Human eyes are more sensitive to green than blue.
        # ----------------------------------------------------

        brightness = (
            0.2126 * frame[:, :, 0]
            + 0.7152 * frame[:, :, 1]
            + 0.0722 * frame[:, :, 2]
        )

        # ----------------------------------------------------
        # DITHERING
        # ----------------------------------------------------

        brightness = self.apply_dither(
            brightness
        )

        # ----------------------------------------------------
        # Convert brightness → character index
        # ----------------------------------------------------

        indexes = self.brightness_to_chars(
            brightness
        )

        # ----------------------------------------------------
        # Build terminal frame
        # ----------------------------------------------------

        output = []

        # Move cursor to top-left.
        output.append(
            "\033[H"
        )

        for y in range(height):

            line = []

            for x in range(width):

                r = int(
                    frame[y, x, 0]
                )

                g = int(
                    frame[y, x, 1]
                )

                b = int(
                    frame[y, x, 2]
                )

                character = self.chars[
                    indexes[y, x]
                ]

                # ------------------------------------------------
                # ANSI TRUE COLOR
                # ------------------------------------------------

                line.append(
                    f"\033[38;2;"
                    f"{r};{g};{b}m"
                    f"{character}"
                )

            # Reset color at end of line.
            line.append(
                "\033[0m"
            )

            output.append(
                "".join(line)
            )

        # ----------------------------------------------------
        # Print complete frame
        # ----------------------------------------------------

        sys.stdout.write(
            "\n".join(output)
        )

        sys.stdout.flush()