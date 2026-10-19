/* SMARTMOP - status-koneksi.js
   Menentukan status robot dari kondisi nyata:
   1) server backend bisa dihubungi?   2) ESP32 masih mengirim heartbeat?   */
(function () {
    const el = document.getElementById("statStatus");
    const sub = document.getElementById("statStatusSub");
    if (!el) return;

    const INTERVAL = 3000;      // cek tiap 3 detik
    const BATAS_GAGAL = 2;      // butuh 2 kegagalan beruntun sebelum "Server terputus" (anti kedip)

    const KEADAAN = {
        cek:        { teks: "Mengecek...",    info: "Menghubungkan ke server",                 kelas: "checking" },
        online:     { teks: "Online",         info: "Server dan robot terhubung",              kelas: "good" },
        robotMati:  { teks: "Robot offline",  info: "Server aktif, ESP32 tidak mengirim sinyal", kelas: "bad" },
        serverMati: { teks: "Server terputus", info: "Backend tidak dapat dihubungi",          kelas: "bad" }
    };

    // Elemen level sabun & baterai
    const SENSOR = {
        sabun:   { teks: document.getElementById("soapValue"),    bar: document.getElementById("soapBar"),    dasar: "" },
        baterai: { teks: document.getElementById("batteryValue"), bar: document.getElementById("batteryBar"), dasar: "green" }
    };

    // nilai berupa angka 0-100 dari sensor, atau null bila tidak ada data
    function isiSensor(s, nilai) {
        if (!s.teks || !s.bar) return;
        const valid = typeof nilai === "number" && isFinite(nilai);
        const v = valid ? Math.max(0, Math.min(100, Math.round(nilai))) : null;
        s.teks.textContent = v === null ? "--" : v + "%";
        s.teks.classList.toggle("off", v === null);
        s.bar.style.width = (v === null ? 0 : v) + "%";
        const wadah = s.bar.parentElement;
        wadah.className = "progress " + (v === null ? "" : v < 15 ? "low" : v < 30 ? "warn" : s.dasar);
        wadah.setAttribute("aria-valuenow", v === null ? "" : v);
        wadah.setAttribute("aria-valuetext", v === null ? "Tidak ada data" : v + " persen");
    }

    function alamatApi() {
        let s = {};
        try { s = JSON.parse(localStorage.getItem("smartmop.settings") || "{}"); } catch (e) {}
        return `http://${s.serverIP || location.hostname || "localhost"}:${s.apiPort || 5000}${s.apiPath || "/api"}`;
    }

    function tampilkan(kunci, data) {
        const k = KEADAAN[kunci];
        el.textContent = k.teks;
        el.className = k.kelas;
        if (sub) sub.textContent = k.info;
        // Sensor hanya ditampilkan saat robot benar-benar online
        const d = kunci === "online" && data ? data : {};
        isiSensor(SENSOR.sabun, d.soap);
        isiSensor(SENSOR.baterai, d.battery);
        // Beri tahu bagian lain (mis. titik status di topbar)
        if (window.SM && SM.setOnline) SM.setOnline(kunci === "online");
        document.dispatchEvent(new CustomEvent("sm:koneksi", { detail: { keadaan: kunci, data: data || null } }));
    }

    let gagal = 0;
    async function cek() {
        const batas = new AbortController();
        const timer = setTimeout(() => batas.abort(), 2500);
        try {
            const res = await fetch(alamatApi() + "/robot/status", { signal: batas.signal, cache: "no-store" });
            if (!res.ok) throw new Error(res.status);
            const data = await res.json();
            gagal = 0;
            tampilkan(data.robot_online ? "online" : "robotMati", data);
        } catch (e) {
            gagal++;
            if (gagal >= BATAS_GAGAL) tampilkan("serverMati");
        } finally {
            clearTimeout(timer);
        }
    }

    tampilkan("cek");
    cek();
    setInterval(cek, INTERVAL);
})();
