import json
import subprocess
import sys
import time
import shutil

import numpy as np


# ============================================================
# DENSE ASCII CHARACTER SET
# DARK -> BRIGHT
# ============================================================

CHARSET = (
    " .'`^\",:;Il!i~+_-?][}{1)(|\\/"
    "tfjrxnuvczXYUJCLQ0OZmwqpdbkhao"
    "*#MW&8%B@$"
)


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_WIDTH = 170

# Terminal character aspect correction.
#
# 0.50 = smaller vertically
# 0.60 = larger
# 0.70 = much larger
#
DEFAULT_HEIGHT_FACTOR = 0.45

# Maximum rendering FPS.
#
# 20 is a good compromise for large ASCII frames.
MAX_FPS = 20

# RGB quantization.
#
# 256 = maximum color precision
# 64  = good quality / performance
# 32  = faster
#
COLOR_LEVELS = 64

# Image adjustment
BRIGHTNESS = 1.05
CONTRAST = 1.15

# Enable ordered dithering
DITHER = True


# ============================================================
# FFPROBE
# ============================================================

def get_video_info(video_path):

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

        fps = (
            float(numerator)
            / max(float(denominator), 1.0)
        )

    else:

        fps = float(fps_text)

    return {
        "width": width,
        "height": height,
        "fps": fps,
    }


# ============================================================
# FFmpeg
# ============================================================

def build_ffmpeg_command(
    video_path,
    width,
    height,
    fps,
):

    filter_string = (
        f"fps={fps:.6f},"
        f"scale={width}:{height}:flags=bilinear"
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


# ============================================================
# AUDIO
# ============================================================

def start_audio(video_path):

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


# ============================================================
# ASCII RENDERER
# ============================================================

class VideoASCIIRenderer:

    def __init__(
        self,

        width=DEFAULT_WIDTH,

        chars=CHARSET,

        brightness=BRIGHTNESS,

        contrast=CONTRAST,

        height_factor=DEFAULT_HEIGHT_FACTOR,

        max_fps=MAX_FPS,
    ):

        self.target_width = max(
            20,
            int(width),
        )

        self.chars = chars

        self.brightness = float(
            brightness
        )

        self.contrast = float(
            contrast
        )

        self.height_factor = float(
            height_factor
        )

        self.max_fps = float(
            max_fps
        )

        # ----------------------------------------------------
        # Cache for ANSI color sequences
        # ----------------------------------------------------

        self.color_cache = {}

        # ----------------------------------------------------
        # Character lookup table
        # ----------------------------------------------------

        self.character_table = np.array(
            list(self.chars),
            dtype="<U1",
        )

        # ----------------------------------------------------
        # Terminal size
        # ----------------------------------------------------

        self.terminal_width = (
            shutil.get_terminal_size(
                fallback=(160, 50)
            ).columns
        )

        self.last_frame_time = 0.0

        self.frame_count = 0

    # ========================================================
    # SIZE
    # ========================================================

    def calculate_size(
        self,
        video_width,
        video_height,
    ):

        width = self.target_width

        aspect_ratio = (
            video_height
            / max(video_width, 1)
        )

        height = int(
            width
            * aspect_ratio
            * self.height_factor
        )

        height = max(
            2,
            height,
        )

        return width, height

    # ========================================================
    # IMAGE ADJUSTMENT
    # ========================================================

    def adjust_image(self, frame):

        # Convert to float only once.
        image = frame.astype(
            np.float32
        )

        # Contrast
        image = (
            (image - 127.5)
            * self.contrast
            + 127.5
        )

        # Brightness
        image *= self.brightness

        return np.clip(
            image,
            0,
            255,
        ).astype(
            np.uint8
        )

    # ========================================================
    # DITHERING
    # ========================================================

    def apply_dither(
        self,
        brightness,
    ):

        if not DITHER:
            return brightness

        pattern = np.array(
            [
                [0, 2],
                [3, 1],
            ],
            dtype=np.float32,
        )

        pattern = (
            pattern / 4.0
            - 0.5
        ) * 8.0

        h, w = brightness.shape

        tiled = np.tile(
            pattern,
            (
                h // 2 + 1,
                w // 2 + 1,
            ),
        )

        tiled = tiled[
            :h,
            :w,
        ]

        return np.clip(
            brightness + tiled,
            0,
            255,
        )

    # ========================================================
    # BRIGHTNESS -> ASCII
    # ========================================================

    def brightness_to_characters(
        self,
        brightness,
    ):

        indexes = (
            brightness
            * (
                len(self.chars) - 1
            )
            / 255.0
        ).astype(
            np.int16
        )

        indexes = np.clip(
            indexes,
            0,
            len(self.chars) - 1,
        )

        return self.character_table[
            indexes
        ]

    # ========================================================
    # COLOR QUANTIZATION
    # ========================================================

    def quantize_colors(
        self,
        frame,
    ):

        # Reducing color precision dramatically
        # reduces the number of different ANSI
        # sequences we need to generate.

        levels = COLOR_LEVELS

        quantized = (
            frame.astype(
                np.uint16
            )
            * levels
            // 256
        )

        quantized = (
            quantized
            * 255
            // max(levels - 1, 1)
        )

        return quantized.astype(
            np.uint8
        )

    # ========================================================
    # ANSI COLOR CACHE
    # ========================================================

    def get_color_code(
        self,
        r,
        g,
        b,
    ):

        key = (
            int(r),
            int(g),
            int(b),
        )

        cached = self.color_cache.get(
            key
        )

        if cached is not None:
            return cached

        code = (
            f"\033[38;2;"
            f"{key[0]};"
            f"{key[1]};"
            f"{key[2]}m"
        )

        self.color_cache[key] = code

        return code

    # ========================================================
    # RENDER FRAME
    # ========================================================

    def render(
        self,
        raw,
        width,
        height,
    ):

        # ----------------------------------------------------
        # Frame rate limiter
        # ----------------------------------------------------

        now = time.perf_counter()

        frame_interval = (
            1.0 / self.max_fps
        )

        if (
            now - self.last_frame_time
            < frame_interval
        ):

            return

        self.last_frame_time = now

        # ----------------------------------------------------
        # Expected frame size
        # ----------------------------------------------------

        expected_size = (
            width
            * height
            * 3
        )

        if len(raw) < expected_size:
            return

        # ----------------------------------------------------
        # Raw RGB -> NumPy
        # ----------------------------------------------------

        frame = np.frombuffer(
            raw[
                :expected_size
            ],
            dtype=np.uint8,
        ).reshape(
            height,
            width,
            3,
        )

        # ----------------------------------------------------
        # Adjust image
        # ----------------------------------------------------

        frame = self.adjust_image(
            frame
        )

        # ----------------------------------------------------
        # Brightness
        # ----------------------------------------------------

        brightness = (
            frame[:, :, 0]
            * 0.2126
            +
            frame[:, :, 1]
            * 0.7152
            +
            frame[:, :, 2]
            * 0.0722
        )

        # ----------------------------------------------------
        # Dithering
        # ----------------------------------------------------

        brightness = self.apply_dither(
            brightness
        )

        # ----------------------------------------------------
        # Characters
        # ----------------------------------------------------

        characters = (
            self.brightness_to_characters(
                brightness
            )
        )

        # ----------------------------------------------------
        # Reduce colors
        # ----------------------------------------------------

        colors = self.quantize_colors(
            frame
        )

        # ----------------------------------------------------
        # Build output
        # ----------------------------------------------------

        output = []

        # Cursor home
        output.append(
            "\033[H"
        )

        # Current ANSI color
        current_color = None

        for y in range(height):

            row_parts = []

            row_chars = characters[y]

            row_colors = colors[y]

            for x in range(width):

                r = int(
                    row_colors[x, 0]
                )

                g = int(
                    row_colors[x, 1]
                )

                b = int(
                    row_colors[x, 2]
                )

                color = (
                    r,
                    g,
                    b,
                )

                # ------------------------------------------------
                # Only send ANSI color when it changes.
                # ------------------------------------------------

                if color != current_color:

                    row_parts.append(
                        self.get_color_code(
                            r,
                            g,
                            b,
                        )
                    )

                    current_color = color

                row_parts.append(
                    row_chars[x]
                )

            row_parts.append(
                "\033[0m"
            )

            output.append(
                "".join(row_parts)
            )

        # ----------------------------------------------------
        # One large write instead of thousands
        # of individual writes.
        # ----------------------------------------------------

        sys.stdout.write(
            "\n".join(output)
        )

        sys.stdout.flush()

        self.frame_count += 1


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    print(
        "video_ascii.py is a rendering module."
    )

    print(
        "Run the project through main.py."
    )