import yt_dlp
import os
import re

def sanitize_filename(name):
    # Loại bỏ các ký tự gây lỗi hoặc không hợp lệ
    return re.sub(r'[\\/*?:"<>|｜]', '_', name)

def download_youtube(url, download_path="downloads"):
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{download_path}/%(title)s.%(ext)s'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'video')
        ext = info.get('ext', 'mp4')

        # Làm sạch tên file
        safe_title = sanitize_filename(title)
        safe_filename = f"{safe_title}.{ext}"

        # Nếu file gốc không khớp thì rename lại
        original_file = os.path.join(download_path, f"{title}.{ext}")
        new_file = os.path.join(download_path, safe_filename)

        # Đổi tên nếu khác
        if os.path.exists(original_file) and original_file != new_file:
            os.rename(original_file, new_file)

        return safe_filename

