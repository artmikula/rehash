import os
import random
import subprocess
import uuid
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp/hashchanger/uploads"
OUTPUT_FOLDER = "/tmp/hashchanger/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_ffmpeg_command(input_path, output_path):
    hue = random.uniform(1.5, 3.5)
    saturation = random.uniform(1.02, 1.08)
    brightness = random.uniform(0.01, 0.03)
    contrast = random.uniform(1.01, 1.04)
    crop_pct = random.uniform(0.96, 0.985)
    crop_x = random.randint(5, 20)
    crop_y = random.randint(5, 20)
    speed = random.choice([0.97, 0.98, 0.99, 1.01, 1.02, 1.03])
    audio_tempo = round(1 / speed, 4)
    crf = random.randint(20, 25)

    vf_filters = (
        f"crop=iw*{crop_pct:.3f}:ih*{crop_pct:.3f}:{crop_x}:{crop_y},"
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        f"hue=h={hue:.2f}:s={saturation:.3f},"
        f"eq=brightness={brightness:.3f}:contrast={contrast:.3f},"
        f"setpts={speed:.3f}*PTS"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filters,
        "-af", f"atempo={audio_tempo}",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]

    return cmd, {
        "hue_shift": round(hue, 2),
        "saturation": round(saturation, 3),
        "brightness": round(brightness, 3),
        "contrast": round(contrast, 3),
        "crop_pct": round(crop_pct * 100, 1),
        "speed_factor": speed,
        "crf": crf,
    }


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/process", methods=["POST"])
def process_video():
    if "video" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    uid = str(uuid.uuid4())[:8]
    input_filename = f"{uid}_input.{ext}"
    output_filename = f"{uid}_rehashed.{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    file.save(input_path)

    cmd, params = build_ffmpeg_command(input_path, output_path)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return jsonify({"error": "FFmpeg failed", "details": result.stderr[-1000:]}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Processing timed out"}), 500
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"rehashed_{file.filename}",
        mimetype=f"video/{ext}"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
