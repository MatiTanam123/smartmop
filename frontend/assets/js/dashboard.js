/* SMARTMOP - dashboard.js (untuk index.html versi sederhana)
   Mengubah keterangan saat Mode Robot diganti, menyimpannya,
   dan mengirimnya ke backend (POST /api/robot/mode). */
(function () {
    const select = document.getElementById("modeRobot");
    const info = document.getElementById("infoMode");
    if (!select || !info) return;

    const KUNCI = "smartmop.modeRobot";
    const PESAN = {
        Otomatis: "Robot berjalan secara otomatis.",
        Manual: "Robot dikendalikan secara manual."
    };

    // Alamat backend: ambil dari Pengaturan bila ada, kalau tidak pakai localhost:5000
    function alamatApi() {
        let s = {};
        try { s = JSON.parse(localStorage.getItem("smartmop.settings") || "{}"); } catch (e) {}
        return `http://${s.serverIP || location.hostname || "localhost"}:${s.apiPort || 5000}${s.apiPath || "/api"}`;
    }

    function tampilkan(mode, terkirim) {
        info.textContent = PESAN[mode] + (terkirim === false ? " (server belum terhubung)" : "");
        info.classList.toggle("otomatis", mode === "Otomatis");
        info.classList.toggle("manual", mode === "Manual");
    }

    async function kirim(mode) {
        const batas = new AbortController();
        const timer = setTimeout(() => batas.abort(), 2000);
        try {
            const res = await fetch(alamatApi() + "/robot/mode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode }),
                signal: batas.signal
            });
            return res.ok;
        } catch (e) {
            return false;
        } finally {
            clearTimeout(timer);
        }
    }

    select.addEventListener("change", async () => {
        const mode = select.value;
        localStorage.setItem(KUNCI, mode);
        tampilkan(mode);
        const ok = await kirim(mode);
        if (select.value === mode) tampilkan(mode, ok);
    });

    // Pulihkan mode terakhir saat halaman dibuka lagi
    const tersimpan = localStorage.getItem(KUNCI);
    if (PESAN[tersimpan]) select.value = tersimpan;
    tampilkan(select.value);
})();