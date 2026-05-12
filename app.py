import os
import random
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename

CAMERA_PROFILES = [
    ("Apple", "iPhone 15 Pro"),
    ("Apple", "iPhone 14"),
    ("Apple", "iPhone 13"),
    ("samsung", "SM-S928U"),
    ("samsung", "SM-S918B"),
    ("Google", "Pixel 8 Pro"),
    ("Google", "Pixel 7"),
]

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp/hashchanger/uploads"
OUTPUT_FOLDER = "/tmp/hashchanger/outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def has_audio_stream(input_path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", input_path],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() == "audio"
    except Exception:
        return False


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

    grain = random.randint(6, 12)
    lens_k1 = random.uniform(-0.03, -0.01)
    lens_k2 = random.uniform(0.005, 0.02)
    blur_center = random.uniform(0.65, 0.78)
    blur_side = round((1 - blur_center) / 2, 3)
    hiss_amp = random.uniform(0.002, 0.005)

    make, model = random.choice(CAMERA_PROFILES)
    capture_dt = datetime.now(timezone.utc) - timedelta(
        days=random.randint(1, 45),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    capture_iso = capture_dt.strftime("%Y-%m-%dT%H:%M:%S")

    video_chain = (
        f"[0:v]crop=iw*{crop_pct:.3f}:ih*{crop_pct:.3f}:{crop_x}:{crop_y},"
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        f"hue=h={hue:.2f}:s={saturation:.3f},"
        f"eq=brightness={brightness:.3f}:contrast={contrast:.3f},"
        f"lenscorrection=k1={lens_k1:.3f}:k2={lens_k2:.3f},"
        f"tmix=frames=3:weights='{blur_side} {blur_center:.3f} {blur_side}',"
        f"noise=alls={grain}:allf=t+u,"
        f"setpts={speed:.3f}*PTS[v]"
    )

    has_audio = has_audio_stream(input_path)
    if has_audio:
        audio_chain = (
            f"[0:a]atempo={audio_tempo}[aclean];"
            f"anoisesrc=color=pink:amplitude={hiss_amp:.4f}:duration=600[hiss];"
            f"[aclean][hiss]amix=inputs=2:duration=first:weights='1 0.6',"
            f"alimiter=limit=0.95[a]"
        )
        filter_complex = f"{video_chain};{audio_chain}"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        filter_complex = video_chain
        maps = ["-map", "[v]"]

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        *maps,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "fast",
        "-g", str(random.randint(48, 96)),
        "-keyint_min", str(random.randint(24, 48)),
        "-c:a", "aac",
        "-b:a", "128k",
        "-metadata", f"make={make}",
        "-metadata", f"model={model}",
        "-metadata", f"creation_time={capture_iso}",
        "-metadata", f"com.apple.quicktime.make={make}",
        "-metadata", f"com.apple.quicktime.model={model}",
        "-metadata", f"com.apple.quicktime.creationdate={capture_iso}",
        "-movflags", "+faststart+use_metadata_tags",
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
        "grain": grain,
        "lens_k1": round(lens_k1, 3),
        "hiss_amp": round(hiss_amp, 4),
        "camera": f"{make} {model}",
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
