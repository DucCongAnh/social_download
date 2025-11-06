document.getElementById("downloadForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const url = document.getElementById("url").value.trim();
    const btn = document.getElementById("downloadBtn");
    const spinner = document.getElementById("loadingSpinner");
    const btnText = document.getElementById("btnText");
    const statusDiv = document.getElementById("status");
    const progressContainer = document.getElementById("progressContainer");
    const progressBar = document.getElementById("progressBar");

    if (!url) {
        statusDiv.textContent = "⚠️ Vui lòng nhập URL video!";
        statusDiv.style.color = "darkorange";
        return;
    }

    btn.disabled = true;
    spinner.classList.remove("d-none");
    btnText.textContent = "Đang tải...";
    statusDiv.textContent = "Đang xử lý video...";
    statusDiv.style.color = "#555";
    progressContainer.classList.remove("d-none");
    progressBar.style.width = "0%";
    progressBar.textContent = "0%";

    try {
        // Gửi yêu cầu bắt đầu tải
        const startRes = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        if (!startRes.ok) throw new Error("Không thể bắt đầu tải!");

        // Theo dõi tiến độ qua SSE
        const eventSource = new EventSource("/api/progress");
        eventSource.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            if (data.status === "downloading") {
                progressBar.style.width = `${data.progress}%`;
                progressBar.textContent = `${Math.round(data.progress)}%`;
            } else if (data.status === "processing") {
                progressBar.classList.add("bg-info");
                progressBar.textContent = "Đang xử lý...";
            } else if (data.status === "done") {
                eventSource.close();
                progressBar.style.width = "100%";
                progressBar.textContent = "Hoàn tất 100%";
                statusDiv.textContent = "✅ Tải thành công! Video đã được lưu...";
                statusDiv.style.color = "green";

                const res = await fetch("/api/download_file");
                const blob = await res.blob();
                const urlBlob = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = urlBlob;
                a.download = data.filename || "video.mp4";
                document.body.appendChild(a);
                a.click();
                a.remove();
            } else if (data.status === "error") {
                eventSource.close();
                progressBar.classList.add("bg-danger");
                progressBar.textContent = "Lỗi";
                statusDiv.textContent = "❌ " + (data.message || "Lỗi tải video");
                statusDiv.style.color = "red";
            }
        };
    } catch (error) {
        statusDiv.textContent = "❌ Lỗi: " + error.message;
        statusDiv.style.color = "red";
    } finally {
        btn.disabled = false;
        spinner.classList.add("d-none");
        btnText.textContent = "⬇️ Tải video";
    }
});
