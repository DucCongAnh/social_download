from flask import Flask, render_template, request, jsonify, send_file, Response
import os, yt_dlp, tempfile, re, json, time, threading

app = Flask(__name__, template_folder='templates', static_folder='static')

# Biến toàn cục lưu tiến độ
progress_data = {"progress": 0, "status": "idle"}


def sanitize_filename(name):
    """Xóa ký tự không hợp lệ trên Windows"""
    return re.sub(r'[\\/*?:"<>|׃]', '_', name).strip()


def download_video(url, tmp_dir):
    """Hàm tải video chạy trong luồng riêng"""
    global progress_data
    progress_data = {"progress": 0, "status": "starting"}

    def progress_hook(d):
        global progress_data
        if d["status"] == "downloading":
            raw_percent = d.get("_percent_str", "0.0%")
            # Loại bỏ mã màu ANSI như \x1b[0;94m
            clean_percent = re.sub(r"\x1b\[[0-9;]*m", "", raw_percent)
            try:
                percent = float(clean_percent.strip().replace("%", ""))
            except ValueError:
                percent = 0.0
            progress_data = {"progress": percent, "status": "downloading"}

        elif d["status"] == "finished":
            progress_data = {"progress": 100.0, "status": "processing"}

    try:
        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(tmp_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_color": True,  # ✅ Tắt mã màu để tránh lỗi float
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            ext = info.get("ext", "mp4")

        # Làm sạch tên file
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.{ext}"
        file_path = os.path.join(tmp_dir, filename)

        # Rename file thực tế (vì yt_dlp đôi khi tạo tên không sạch)
        for f in os.listdir(tmp_dir):
            if f.endswith(ext):
                os.rename(os.path.join(tmp_dir, f), file_path)
                break

        progress_data = {
            "progress": 100.0,
            "status": "done",
            "file_path": file_path,
            "filename": filename,
        }

    except Exception as e:
        progress_data = {"progress": 0, "status": "error", "message": str(e)}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url")

    # ✅ Chỉ giữ phần trước dấu & để tránh tải cả playlist
    if url and "youtube.com/watch" in url:
        url = url.split("&")[0]


    if not url:
        return jsonify({"status": "error", "message": "URL không hợp lệ"}), 400

    tmp_dir = tempfile.mkdtemp()
    thread = threading.Thread(target=download_video, args=(url, tmp_dir))
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/progress")
def progress_stream():
    """Luồng SSE cập nhật tiến trình"""
    def generate():
        last_value = -1
        while True:
            if progress_data["status"] in ["done", "error"]:
                yield f"data: {json.dumps(progress_data)}\n\n"
                break

            if progress_data["progress"] != last_value:
                last_value = progress_data["progress"]
                yield f"data: {json.dumps(progress_data)}\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/download_file")
def download_file():
    """Sau khi hoàn tất, client gọi route này để lấy file"""
    if progress_data.get("status") != "done":
        return jsonify({"status": "error", "message": "File chưa sẵn sàng"}), 400

    return send_file(
        progress_data["file_path"],
        as_attachment=True,
        download_name=progress_data["filename"],
        mimetype="video/mp4"
    )


if __name__ == "__main__":
    app.run(debug=True)
