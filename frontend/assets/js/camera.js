/* SMARTMOP - camera.js : halaman Live Camera */
(function (SM) {
    const $ = (id) => document.getElementById(id);
    const pad = (n) => String(n).padStart(2, "0");

    document.addEventListener("DOMContentLoaded", () => {
        const feed = $("mainFeed"); if (!feed) return;
        $("icoPhoto").innerHTML = SM.icon("camera");
        $("icoRec").innerHTML = SM.icon("video");
        $("icoFull").innerHTML = SM.icon("expand");

        // Video asli dari ESP32-CAM (bila IP diisi). Jika gagal, tampilan simulasi tetap dipakai.
        const ip = SM.settings().cameraIP;
        let img = null;
        if (ip) {
            img = new Image();
            img.className = "stream"; img.alt = "Video langsung ESP32-CAM"; img.crossOrigin = "anonymous";
            img.onload = () => { feed.classList.add("live"); $("camInfo").textContent = "Terhubung ke ESP32-CAM (" + ip + ")."; };
            img.onerror = () => { $("camInfo").textContent = "ESP32-CAM di " + ip + " tidak merespons. Menampilkan simulasi."; };
            img.src = `http://${ip}:81/stream`;
            feed.prepend(img);
        }

        $("btnPhoto").addEventListener("click", () => {
            if (feed.classList.contains("live")) {
                try {
                    const c = document.createElement("canvas");
                    c.width = img.naturalWidth; c.height = img.naturalHeight;
                    c.getContext("2d").drawImage(img, 0, 0);
                    const a = document.createElement("a");
                    a.href = c.toDataURL("image/jpeg", 0.92);
                    a.download = `smartmop-${Date.now()}.jpg`; a.click();
                    return SM.toast("Foto disimpan.", "success");
                } catch (e) { return SM.toast("Foto gagal diambil dari stream.", "error"); }
            }
            SM.toast("Mode simulasi: foto belum bisa disimpan.", "warn");
        });

        let rec = null, sec = 0;
        $("btnRec").addEventListener("click", (e) => {
            const on = !rec;
            e.currentTarget.setAttribute("aria-pressed", on);
            if (on) {
                sec = 0;
                rec = setInterval(() => { sec++; $("recLabel").textContent = `${pad(Math.floor(sec / 60))}:${pad(sec % 60)}`; }, 1000);
                $("recLabel").textContent = "00:00";
                SM.toast("Perekaman dimulai.");
            } else {
                clearInterval(rec); rec = null; $("recLabel").textContent = "Rekam";
                SM.toast("Perekaman dihentikan.");
            }
        });

        $("btnHD").addEventListener("click", (e) => {
            const hd = e.currentTarget.getAttribute("aria-pressed") !== "true";
            e.currentTarget.setAttribute("aria-pressed", hd);
            $("hdTag").textContent = hd ? "SD" : "HD";
            SM.api("/camera/quality", { method: "POST", body: { quality: hd ? "SD" : "HD" } });
        });

        $("btnFull").addEventListener("click", () => {
            if (document.fullscreenElement) document.exitFullscreen();
            else feed.requestFullscreen?.();
        });
    });
})(window.SM);
