
/* =========================================
   SMARTMOP - STATUS SISTEM
   ========================================= */

document.addEventListener("DOMContentLoaded", () => {

    const apiState = document.getElementById("apiState");
    const apiNote = document.getElementById("apiNote");
    const robotState = document.getElementById("robotState");
    const robotNote = document.getElementById("robotNote");

    const refreshButton = document.getElementById("refreshStatus");
    const clearButton = document.getElementById("clearLogs");
    const logsContainer = document.getElementById("systemLogs");
    const apiAddress = document.getElementById("apiAddress");

    // Sesuaikan dengan alamat backend SmartMop
    const API_BASE = window.API_BASE_URL || "http://localhost:8000";

    apiAddress.textContent = "Alamat backend: " + API_BASE;

    // Menambahkan catatan log
    function addLog(message) {
        const emptyMessage = logsContainer.querySelector(".sm-muted");

        if (emptyMessage) {
            emptyMessage.remove();
        }

        const logItem = document.createElement("div");
        logItem.className = "sm-log-item";

        const logText = document.createElement("span");
        logText.textContent = message;

        const logTime = document.createElement("span");
        logTime.className = "sm-log-time";
        logTime.textContent = new Date().toLocaleTimeString("id-ID");

        logItem.appendChild(logText);
        logItem.appendChild(logTime);

        logsContainer.prepend(logItem);
    }

    // Mengubah tampilan status
    function updateStatus(element, text, statusClass) {
        element.textContent = text;

        element.classList.remove(
            "sm-online",
            "sm-offline",
            "sm-unknown"
        );

        element.classList.add(statusClass);
    }

    // Memeriksa koneksi backend
    async function checkConnection() {
        refreshButton.disabled = true;
        refreshButton.textContent = "Memeriksa...";

        updateStatus(apiState, "Memeriksa...", "sm-unknown");

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);

        try {
            const response = await fetch(API_BASE + "/health", {
                method: "GET",
                signal: controller.signal,
                cache: "no-store"
            });

            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }

            updateStatus(apiState, "Terhubung", "sm-online");
            apiNote.textContent = "Backend merespons pemeriksaan";

            addLog("Pemeriksaan koneksi backend berhasil.");

            // Koneksi API bukan berarti robot online
            updateStatus(robotState, "Belum diketahui", "sm-unknown");
            robotNote.textContent = "Menunggu data status robot";

        } catch (error) {
            updateStatus(apiState, "Tidak terhubung", "sm-offline");

            apiNote.textContent = "Backend tidak dapat diakses";

            updateStatus(robotState, "Belum diketahui", "sm-unknown");
            robotNote.textContent = "Status robot belum dapat diverifikasi";

            addLog("Pemeriksaan backend gagal: " + error.message);

        } finally {
            clearTimeout(timeout);
            refreshButton.disabled = false;
            refreshButton.textContent = "Periksa Koneksi";
        }
    }

    // Tombol periksa koneksi
    refreshButton.addEventListener("click", checkConnection);

    // Tombol bersihkan log
    clearButton.addEventListener("click", () => {
        logsContainer.innerHTML =
            '<p class="sm-muted">Belum ada aktivitas yang tercatat.</p>';
    });

    // Log ketika halaman dibuka
    addLog("Halaman Status Sistem dibuka.");

});
