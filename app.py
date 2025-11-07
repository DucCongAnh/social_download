from flask import Flask, render_template, request, jsonify, send_file, Response
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from urllib.parse import urlparse

import yt_dlp

app = Flask(__name__, template_folder='templates', static_folder='static')

# Lưu trạng thái tải theo từng download_id để tránh ghi đè giữa các người dùng
downloads_lock = threading.Lock()
downloads = {}


def init_download(download_id, tmp_dir):
    with downloads_lock:
        downloads[download_id] = {
            "progress": 0.0,
            "status": "starting",
            "filename": None,
            "file_path": None,
            "message": None,
            "tmp_dir": tmp_dir,
        }


def update_download(download_id, **kwargs):
    with downloads_lock:
        if download_id in downloads:
            downloads[download_id].update(kwargs)


def get_download(download_id):
    with downloads_lock:
        entry = downloads.get(download_id)
        return entry.copy() if entry else None


def cleanup_download(download_id, delay=30):
    """Dọn dẹp thư mục tạm sau khi đã gửi file cho client."""

    def _cleanup():
        time.sleep(delay)
        with downloads_lock:
            entry = downloads.pop(download_id, None)
        if entry:
            tmp_dir = entry.get("tmp_dir")
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    threading.Thread(target=_cleanup, daemon=True).start()


def is_valid_url(url):
    """Kiểm tra URL hợp lệ."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except ValueError:
        return False


def sanitize_filename(name):
    """Loại bỏ ký tự không hợp lệ khi tạo tên file."""
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()


def _select_format():
    """Return yt_dlp format string and ffmpeg location depending on availability."""
    ffmpeg_path = shutil.which("ffmpeg") or shutil.which("avconv")
    if ffmpeg_path:
        return {
            "format": "bestvideo+bestaudio/best",
            "ffmpeg_location": os.path.dirname(ffmpeg_path),
            "needs_ffmpeg": True,
        }

    # Fall back to progressive streams (video+audio together) so ffmpeg is not needed.
    progressive = "best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none][vcodec!=none]/best"
    return {"format": progressive, "ffmpeg_location": None, "needs_ffmpeg": False}


def download_video(download_id, url, tmp_dir):
    """Tải video trong luồng riêng cho từng download_id."""
    update_download(download_id, progress=0.0, status="starting")

    def progress_hook(d):
        if d["status"] == "downloading":
            raw_percent = d.get("_percent_str", "0.0%")
            clean_percent = re.sub(r"\x1b\[[0-9;]*m", "", raw_percent)
            try:
                percent = float(clean_percent.strip().replace("%", ""))
            except ValueError:
                percent = 0.0
            update_download(download_id, progress=percent, status="downloading")
        elif d["status"] == "finished":
            update_download(download_id, progress=100.0, status="processing")

    try:
        format_config = _select_format()
        ydl_opts = {
            "format": format_config["format"],
            "outtmpl": os.path.join(tmp_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_color": True,
        }

        if format_config["ffmpeg_location"]:
            ydl_opts["ffmpeg_location"] = format_config["ffmpeg_location"]
        else:
            # Avoid post-processing steps that require ffmpeg when we only have progressive streams.
            ydl_opts["postprocessors"] = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            ext = info.get("ext", "mp4")
            downloaded_file = info.get("_filename")

        safe_title = sanitize_filename(title) or "video"
        filename = f"{safe_title}.{ext}"
        file_path = os.path.join(tmp_dir, filename)

        source_file = downloaded_file if downloaded_file and os.path.exists(downloaded_file) else None
        if not source_file:
            for entry in os.listdir(tmp_dir):
                if entry.endswith(ext):
                    source_file = os.path.join(tmp_dir, entry)
                    break
        if source_file and source_file != file_path:
            os.rename(source_file, file_path)
        elif not source_file:
            raise FileNotFoundError("Không tìm thấy file đã tải xuống")

        update_download(
            download_id,
            progress=100.0,
            status="done",
            file_path=file_path,
            filename=filename,
        )

    except Exception as exc:
        error_text = str(exc)
        if "ffmpeg" in error_text.lower():
            error_text = (
                "May chu khong ho tro dinh dang nay do thieu FFmpeg. "
                "Vui long chon video khac hoac thu video co chat luong thap hon."
            )
        update_download(download_id, progress=0.0, status="error", message=error_text)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/get_info", methods=["POST"])
def get_video_info():
    data = request.get_json()
    url = data.get("url") if data else None
    if not url or not is_valid_url(url):
        return jsonify({"status": "error", "message": "Link không hợp lệ!"}), 400

    if "youtube.com/watch" in url:
        url = url.split("&")[0]

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        thumbnail = info.get("thumbnail", "")
        if not thumbnail and info.get("thumbnails"):
            thumbnail = info["thumbnails"][-1]["url"]

        return jsonify(
            {
                "status": "success",
                "title": info.get("title", "Video"),
                "thumbnail": thumbnail,
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
            }
        )
    except Exception as exc:
        error_text = str(exc)
        if "Unsupported URL" in error_text:
            user_message = "Link này không được hỗ trợ. Hãy nhập link video!"
        elif "HTTP Error 403" in error_text:
            user_message = "Máy chủ chặn truy cập. Có thể video riêng tư hoặc bị giới hạn vùng."
        elif "Video unavailable" in error_text:
            user_message = "Video không tồn tại hoặc đã bị xóa."
        else:
            user_message = "Đã xảy ra lỗi. Vui lòng thử lại sau."
        return jsonify({"status": "error", "message": user_message}), 400


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url") if data else None
    if not url or not is_valid_url(url):
        return jsonify({"status": "error", "message": "Link không hợp lệ!"}), 400

    if "youtube.com/watch" in url:
        url = url.split("&")[0]

    tmp_dir = tempfile.mkdtemp()
    download_id = uuid.uuid4().hex
    init_download(download_id, tmp_dir)

    thread = threading.Thread(target=download_video, args=(download_id, url, tmp_dir), daemon=True)
    thread.start()

    return jsonify({"status": "started", "download_id": download_id})


@app.route("/api/progress/<download_id>")
def progress_stream(download_id):
    if not get_download(download_id):
        return jsonify({"status": "error", "message": "Download ID không hợp lệ"}), 404

    def generate():
        last_payload = None
        while True:
            entry = get_download(download_id)
            if not entry:
                yield f'data: {json.dumps({"status": "error", "message": "Download ID không còn nữa"})}\n\n'
                break

            payload = {
                "progress": entry.get("progress", 0.0),
                "status": entry.get("status", "idle"),
                "message": entry.get("message"),
                "filename": entry.get("filename"),
            }

            if payload != last_payload:
                last_payload = payload
                yield f"data: {json.dumps(payload)}\n\n"

            if entry.get("status") in ["done", "error"]:
                break

            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/download_file/<download_id>")
def download_file(download_id):
    entry = get_download(download_id)
    if not entry or entry.get("status") != "done":
        return jsonify({"status": "error", "message": "File chưa sẵn sàng"}), 400

    file_path = entry.get("file_path")
    filename = entry.get("filename") or "video.mp4"
    if not file_path or not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "File không tồn tại"}), 400

    response = send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype="video/mp4",
    )

    cleanup_download(download_id)
    return response


if __name__ == "__main__":
    app.run(debug=True)
