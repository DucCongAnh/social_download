# facebook cũng xử lý bằng yt-dlp vì hỗ trợ nhiều site
from yt_dlp import YoutubeDL
import os
import datetime

def download_facebook(url: str, save_dir: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_template = os.path.join(save_dir, f'%(title)s_{ts}.%(ext)s')
    ydl_opts = {
        'outtmpl': out_template,
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return os.path.basename(filename)
