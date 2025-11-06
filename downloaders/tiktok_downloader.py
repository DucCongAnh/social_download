# sử dụng yt-dlp (python API)
from yt_dlp import YoutubeDL
import os
import datetime

def sanitize_filename(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in " .-_").rstrip()

def download_tiktok(url: str, save_dir: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # đặt template tên
    out_template = os.path.join(save_dir, f'%(title)s_{ts}.%(ext)s')
    ydl_opts = {
        'outtmpl': out_template,
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'cookies': 'cookies.txt'   # nếu cần cookie để tải video riêng tư
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # build filename
        filename = ydl.prepare_filename(info)
        # prepare_filename trả về đường dẫn đầy đủ; trả về tên file tương đối
        return os.path.basename(filename)
