/* SMARTMOP - api.js
   Pengaturan tersimpan + pemanggil API. Jika backend belum berjalan,
   data contoh (mock) dipakai agar tampilan tetap bisa dicoba. */
window.SM = window.SM || {};
(function (SM) {
    const KEY = "smartmop.settings";
    SM.defaults = {
        namaRobot: "SmartMop-01", modeAwal: "Otomatis", kecepatan: "Sedang",
        waktuPemotretan: "3", confidence: "0.6", pengulangan: "2", volumeSabun: "Sedang",
        ukuranModel: "640", bbox: true, simpanGambar: true,
        batasBaterai: "20", batasSabun: "15", stopBaterai: true,
        notifWeb: true, notifSuara: true, notifBrowser: false, notifSelesai: true, notifError: true,
        ssid: "", serverIP: "", apiPort: "5000", apiPath: "/api", cameraIP: "", controllerIP: ""
    };
    SM.settings = () => {
        try { return Object.assign({}, SM.defaults, JSON.parse(localStorage.getItem(KEY) || "{}")); }
        catch (e) { return Object.assign({}, SM.defaults); }
    };
    SM.saveSettings = (s) => localStorage.setItem(KEY, JSON.stringify(s));
    SM.apiBase = () => {
        const s = SM.settings();
        return `http://${s.serverIP || location.hostname || "localhost"}:${s.apiPort || 5000}${s.apiPath || "/api"}`;
    };

    SM.api = async function (path, opt = {}) {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 2000);
        try {
            const res = await fetch(SM.apiBase() + path, {
                method: opt.method || "GET", signal: ctl.signal,
                headers: { "Content-Type": "application/json" },
                body: opt.body ? JSON.stringify(opt.body) : undefined
            });
            clearTimeout(timer);
            if (!res.ok) throw new Error(res.status);
            SM.demo = false;
            return await res.json();
        } catch (e) {
            clearTimeout(timer);
            SM.demo = true;
            if (!SM._warned && SM.toast) {
                SM._warned = true;
                SM.toast("Server belum terhubung. Menampilkan data contoh.", "warn");
            }
            return SM.mock(path, opt);
        }
    };

    /* ---------- Data contoh ---------- */
    const pad = (n) => String(n).padStart(2, "0");
    const ago = (min) => { const d = new Date(Date.now() - min * 60000); return d; };
    const hm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

    SM.mock = function (path) {
        if (path.startsWith("/dashboard")) {
            return {
                robot: { status: "Online", mode: "Otomatis", soap: 68, battery: 85 },
                detections: [
                    { label: "Tumpahan Sirup", confidence: 87, time: hm(ago(0)), spill: true, status: "Menunggu Pembersihan" },
                    { label: "Tidak Ada Tumpahan", confidence: 96, time: hm(ago(1)), spill: false, status: "Lantai Bersih" }
                ],
                log: [
                    { time: hm(ago(0)), text: "Tumpahan terdeteksi (87%)", type: "danger" },
                    { time: hm(ago(0)), text: "Robot bergerak menuju lokasi", type: "info" },
                    { time: hm(ago(0)), text: "Proses mengepel", type: "info" },
                    { time: hm(ago(60)), text: "Pembersihan selesai", type: "success" },
                    { time: hm(ago(120)), text: "Lantai bersih (96%)", type: "success" }
                ]
            };
        }
        if (path.startsWith("/history")) {
            const rows = [
                [0, "Tumpahan Sirup", 87, "Dibersihkan"], [14, "Tidak Ada Tumpahan", 96, "-"],
                [38, "Tumpahan Sirup", 82, "Dibersihkan"], [55, "Tidak Ada Tumpahan", 98, "-"],
                [92, "Tumpahan Sirup", 90, "Dibersihkan"], [140, "Tumpahan Sirup", 74, "Gagal"],
                [1500, "Tumpahan Sirup", 91, "Dibersihkan"], [1530, "Tidak Ada Tumpahan", 95, "-"]
            ];
            return rows.map((r, i) => {
                const d = ago(r[0]);
                return { id: i + 1, date: ymd(d), time: hm(d), label: r[1], spill: r[1] !== "Tidak Ada Tumpahan", confidence: r[2], status: r[3] };
            });
        }
        return { ok: true, mock: true };
    };
})(window.SM);
