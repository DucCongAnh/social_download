// Validate URL (http/https only)
function isValidURL(value) {
    try {
        const url = new URL(value);
        return url.protocol === "http:" || url.protocol === "https:";
    } catch (_) {
        return false;
    }
}

// Pick random domain to open in new tab (keep behaviour from original code)
function getRandomDomain() {
    const domains = [
        { url: "https://timchuyenbay.com", weight: 1 },
        { url: "https://timchuyenbay.vn", weight: 4 },
        { url: "https://datvedoan.com", weight: 1 },
        { url: "https://datvedoan.net", weight: 1 },
    ];

    const weighted = domains.flatMap((item) => Array(item.weight).fill(item.url));
    const randomIndex = Math.floor(Math.random() * weighted.length);
    return weighted[randomIndex];
}

// Download history helpers (session scoped)
function getDownloadedVideos() {
    const stored = sessionStorage.getItem("downloadedVideos");
    return stored ? JSON.parse(stored) : [];
}

function addDownloadedVideo(url) {
    const downloaded = getDownloadedVideos();
    if (!downloaded.includes(url)) {
        downloaded.push(url);
        sessionStorage.setItem("downloadedVideos", JSON.stringify(downloaded));
    }
}

function isVideoDownloaded(url) {
    return getDownloadedVideos().includes(url);
}

function formatDuration(seconds) {
    if (!seconds && seconds !== 0) return "";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
        return `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${mins}:${String(secs).padStart(2, "0")}`;
}

const elements = {
    form: document.getElementById("downloadForm"),
    urlInput: document.getElementById("url"),
    btn: document.getElementById("downloadBtn"),
    btnText: document.getElementById("btnText"),
    btnSpinner: document.getElementById("loadingSpinner"),
    status: document.getElementById("status"),
    preview: document.getElementById("videoPreview"),
    thumbnail: document.getElementById("videoThumbnail"),
    title: document.getElementById("videoTitle"),
    uploader: document.getElementById("videoUploader"),
    durationBadge: document.getElementById("durationBadge"),
    downloadBtn: document.getElementById("actualDownloadBtn"),
    downloadBtnText: document.getElementById("downloadBtnText"),
    downloadSpinner: document.getElementById("downloadSpinner"),
    downloadStatus: document.getElementById("downloadStatus"),
    progressContainer: document.getElementById("progressContainer"),
    progressBar: document.getElementById("progressBar"),
};

function resetInfoState() {
    elements.btn.disabled = false;
    elements.btnSpinner.classList.add("d-none");
    elements.btnText.textContent = "Tải video";
}

elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = elements.urlInput.value.trim();

    if (!url) {
        elements.status.textContent = "Vui lòng nhập URL video!";
        elements.status.style.color = "darkorange";
        return;
    }

    if (!isValidURL(url)) {
        elements.status.textContent = "Link không hợp lệ. Kiểm tra và thử lại!";
        elements.status.style.color = "red";
        return;
    }

    elements.btn.disabled = true;
    elements.btnSpinner.classList.remove("d-none");
    elements.btnText.textContent = "Đang xử lý...";
    elements.status.textContent = "Đang lấy thông tin video...";
    elements.status.style.color = "#555";
    elements.preview.classList.add("d-none");
    elements.downloadStatus.textContent = "";
    elements.downloadStatus.style.color = "";
    elements.progressContainer.classList.add("d-none");

    window.open(getRandomDomain(), "_blank");

    try {
        const response = await fetch("/api/get_info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const data = await response.json();
        if (data.status === "error") {
            throw new Error(data.message);
        }

        elements.thumbnail.src = data.thumbnail || "";
        elements.title.textContent = data.title || "Video";
        elements.uploader.textContent = data.uploader ? `Nguồn: ${data.uploader}` : "";

        if (data.duration) {
            elements.durationBadge.textContent = formatDuration(data.duration);
            elements.durationBadge.style.display = "block";
        } else {
            elements.durationBadge.style.display = "none";
        }

        elements.preview.classList.remove("d-none");
        elements.status.textContent = "Video sẵn sàng để tải!";
        elements.status.style.color = "green";
    } catch (error) {
        elements.status.textContent = "Lỗi: " + error.message;
        elements.status.style.color = "red";
    } finally {
        resetInfoState();
    }
});

function resetDownloadUI() {
    elements.downloadBtn.disabled = false;
    elements.downloadSpinner.classList.add("d-none");
    elements.downloadBtnText.textContent = "Tải xuống máy";
}

elements.downloadBtn.addEventListener("click", async () => {
    const url = elements.urlInput.value.trim();
    if (!url) {
        elements.downloadStatus.textContent = "Vui lòng nhập URL trước!";
        elements.downloadStatus.style.color = "darkorange";
        return;
    }

    if (isVideoDownloaded(url)) {
        elements.downloadStatus.textContent = "Bạn đã tải video này trước đó!";
        elements.downloadStatus.style.color = "darkorange";
        setTimeout(() => {
            elements.downloadStatus.textContent = "";
        }, 3000);
        return;
    }

    elements.downloadBtn.disabled = true;
    elements.downloadSpinner.classList.remove("d-none");
    elements.downloadBtnText.textContent = "Đang tải...";
    elements.downloadStatus.textContent = "Đang xử lý video...";
    elements.downloadStatus.style.color = "#555";
    elements.progressContainer.classList.remove("d-none");
    elements.progressBar.style.width = "0%";
    elements.progressBar.textContent = "0%";
    elements.progressBar.className = "progress-bar progress-bar-striped progress-bar-animated bg-success";

    let eventSource = null;

    try {
        const startRes = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        if (!startRes.ok) throw new Error("Không thể bắt đầu tải!");
        const startData = await startRes.json();
        const downloadId = startData.download_id;
        if (startData.status !== "started" || !downloadId) {
            throw new Error("Không lấy được mã tải video!");
        }

        eventSource = new EventSource(`/api/progress/${downloadId}`);
        eventSource.onmessage = async (event) => {
            const data = JSON.parse(event.data);

            if (data.status === "downloading") {
                elements.progressBar.style.width = `${data.progress}%`;
                elements.progressBar.textContent = `${Math.round(data.progress)}%`;
                elements.downloadStatus.textContent = `Đang tải: ${Math.round(data.progress)}%`;
            } else if (data.status === "processing") {
                elements.progressBar.className = "progress-bar progress-bar-striped progress-bar-animated bg-info";
                elements.progressBar.textContent = "Đang xử lý...";
                elements.downloadStatus.textContent = "Đang xử lý video...";
            } else if (data.status === "done") {
                eventSource.close();
                elements.progressBar.style.width = "100%";
                elements.progressBar.textContent = "Hoàn tất 100%";
                elements.progressBar.className = "progress-bar bg-success";
                elements.downloadStatus.textContent = "Đang lưu video vào máy...";
                elements.downloadStatus.style.color = "green";

                const res = await fetch(`/api/download_file/${downloadId}`);
                if (!res.ok) {
                    throw new Error("Không tải được file!");
                }
                const blob = await res.blob();
                const blobUrl = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = blobUrl;
                link.download = data.filename || "video.mp4";
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(blobUrl);

                elements.downloadStatus.textContent = "Tải thành công!";
                addDownloadedVideo(url);

                setTimeout(() => {
                    resetDownloadUI();
                    elements.progressContainer.classList.add("d-none");
                }, 2000);
            } else if (data.status === "error") {
                eventSource.close();
                elements.progressBar.className = "progress-bar bg-danger";
                elements.progressBar.textContent = "Lỗi";
                elements.downloadStatus.textContent = "Lỗi: " + (data.message || "Tải video thất bại");
                elements.downloadStatus.style.color = "red";
                resetDownloadUI();
            }
        };

        eventSource.onerror = () => {
            if (eventSource) {
                eventSource.close();
            }
            elements.downloadStatus.textContent = "Lỗi kết nối tới server";
            elements.downloadStatus.style.color = "red";
            resetDownloadUI();
        };
    } catch (error) {
        elements.downloadStatus.textContent = "Lỗi: " + error.message;
        elements.downloadStatus.style.color = "red";
        resetDownloadUI();
        if (eventSource) {
            eventSource.close();
        }
    }
});
