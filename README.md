# REHASH

A tiny Flask web app that "rehashes" a video — re-encodes it with small, randomized visual and audio tweaks so the output has a different file hash and perceptual fingerprint than the input. Useful for stress-testing dedupe pipelines, content-ID systems, or just generating fresh-looking copies of a clip you own.

> Only use this on content you have the rights to. Circumventing platform copyright/dedupe systems on third-party material may violate their terms of service or the law.

## What it does

For each upload, the server picks random values within sane ranges for:

- Hue shift, saturation, brightness, contrast
- A small crop + re-pad to 1080×1920
- Playback speed (0.97×–1.03×) with matched audio tempo
- x264 CRF (20–25)

…then runs a single `ffmpeg` pass and returns the re-encoded file.

## Requirements

- Python 3.10+
- `ffmpeg` available on `PATH` (`brew install ffmpeg` on macOS)

## Run

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5050 and drop a video onto the page.

## Supported input formats

`mp4`, `mov`, `avi`, `mkv`, `webm`.

## Project layout

```
app.py            Flask app + ffmpeg command builder
index.html        Single-page upload UI
requirements.txt  Python deps
```

## Notes

- Uploads and outputs live in `/tmp/hashchanger/`. The input is deleted after processing; outputs are not auto-cleaned.
- The encoder is hard-coded to libx264 + AAC, output stretched/letterboxed to 1080×1920 (portrait). Edit `build_ffmpeg_command` in `app.py` to change.
- `debug=True` is on by default — turn it off before exposing this anywhere.
