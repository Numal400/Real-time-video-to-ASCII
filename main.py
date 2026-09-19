import argparse
import os
import shutil
import subprocess
import sys
import time

from video_ascii import VideoASCIIRenderer, get_video_info, build_ffmpeg_command, start_audio


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def hide_cursor():
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\x1b[?25h\x1b[0m\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Real-time colored ASCII video player using FFmpeg + ANSI True Color."
    )
    parser.add_argument("video", help="Path to a video file")
    parser.add_argument("--width", type=int, default=100,
                        help="ASCII width in characters (default: 100)")
    parser.add_argument("--chars", default=" .:-=+*#%@",
                        help="Brightness character ramp")
    parser.add_argument("--no-audio", action="store_true",
                        help="Disable audio playback")
    parser.add_argument("--fps", type=float, default=0,
                        help="Override FPS. 0 = use source FPS")
    parser.add_argument("--brightness", type=float, default=1.0,
                        help="Brightness multiplier (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.0,
                        help="Contrast multiplier (default: 1.0)")
    args = parser.parse_args()

    video_path = os.path.abspath(args.video)

    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        sys.exit(1)

    if shutil.which("ffmpeg") is None:
        print("ERROR: FFmpeg was not found in PATH.")
        print("Install FFmpeg and make sure ffmpeg.exe is available from the terminal.")
        sys.exit(1)

    if not args.no_audio and shutil.which("ffplay") is None:
        print("WARNING: ffplay was not found. Video will run without audio.")
        args.no_audio = True

    try:
        info = get_video_info(video_path)
    except Exception as exc:
        print(f"Could not read video information: {exc}")
        sys.exit(1)

    source_fps = info["fps"]
    fps = args.fps if args.fps > 0 else source_fps

    if fps <= 0:
        fps = 30.0

    renderer = VideoASCIIRenderer(
        width=args.width,
        chars=args.chars,
        brightness=args.brightness,
        contrast=args.contrast,
    )

    width, height = renderer.calculate_size(info["width"], info["height"])

    print("ASCII VIDEO PLAYER")
    print("------------------")
    print(f"Video : {os.path.basename(video_path)}")
    print(f"Source: {info['width']}x{info['height']} @ {source_fps:.2f} FPS")
    print(f"ASCII : {width}x{height} @ {fps:.2f} FPS")
    print()
    print("Controls: Q = quit | + / - = change terminal size")
    print("Starting...")
    time.sleep(1)

    # FFmpeg sends decoded RGB frames to Python.
    cmd = build_ffmpeg_command(video_path, width, height, fps)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=1024 * 1024,
    )

    audio_process = None
    if not args.no_audio:
        audio_process = start_audio(video_path)

    frame_size = width * height * 3
    frame_interval = 1.0 / fps
    next_frame_time = time.perf_counter()

    clear_screen()
    hide_cursor()

    try:
        frame_number = 0

        while True:
            raw = process.stdout.read(frame_size)

            if len(raw) != frame_size:
                break

            frame_number += 1
            renderer.render(raw, width, height)

            # Keep video paced against a monotonic clock.
            next_frame_time += frame_interval
            sleep_for = next_frame_time - time.perf_counter()

            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # If the renderer falls behind, reset the clock instead
                # of accumulating delay forever.
                if sleep_for < -frame_interval * 3:
                    next_frame_time = time.perf_counter()

    except KeyboardInterrupt:
        pass
    finally:
        try:
            process.terminate()
        except Exception:
            pass

        if audio_process is not None:
            try:
                audio_process.terminate()
            except Exception:
                pass

        show_cursor()
        clear_screen()


if __name__ == "__main__":
    main()
