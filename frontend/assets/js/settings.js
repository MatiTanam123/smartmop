/* SMARTMOP - settings.js : halaman Pengaturan (tab, simpan, uji koneksi) */
(function (SM) {
    const $ = (id) => document.getElementById(id);
    const fields = () => document.querySelectorAll("[data-setting]");

    function fill(s) {
        fields().forEach((el) => {
            if (el.type === "checkbox") el.checked = !!s[el.id];
            else el.value = s[el.id] ?? "";
        });
    }
    function collect() {
        const s = {};
        fields().forEach((el) => (s[el.id] = el.type === "checkbox" ? el.checked : el.value.trim()));
        return s;
    }

    function validate(s) {
        const c = parseFloat(s.confidence);
        if (isNaN(c) || c < 0 || c > 1) return ["confidence", "Ambang confidence harus antara 0.0 dan 1.0."];
        const port = parseInt(s.apiPort, 10);
        if (isNaN(port) || port < 1 || port > 65535) return ["apiPort", "Port API harus antara 1 dan 65535."];
        const ip = /^(\d{1,3}\.){3}\d{1,3}$/;
        for (const k of ["serverIP", "cameraIP", "controllerIP"])
            if (s[k] && !ip.test(s[k]) && s[k] !== "localhost") return [k, "Format alamat IP belum benar. Contoh: 192.168.1.10"];
        return null;
    }

    function openTab(name) {
        document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", t.dataset.tab === name));
        document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== name));
        history.replaceState(null, "", "#" + name);
    }

    async function ping(url) {
        const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 2500);
        try { await fetch(url, { mode: "no-cors", signal: ctl.signal }); return true; }
        catch (e) { return false; } finally { clearTimeout(timer); }
    }
    function mark(id, ok, empty) {
        const el = $(id);
        el.className = "connection-indicator " + (empty ? "" : ok ? "ok" : "fail");
        el.textContent = empty ? "IP belum diisi" : ok ? "Terhubung" : "Tidak terjangkau";
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (!$("formPengaturan")) return;
        document.querySelectorAll("[data-icon]").forEach((e) => (e.innerHTML = SM.icon(e.dataset.icon)));
        $("simpanPengaturan").innerHTML = SM.icon("save") + "Simpan Pengaturan";

        fill(SM.settings());
        const start = location.hash.slice(1);
        if ($(start)?.classList.contains("panel")) openTab(start);

        document.querySelector(".tabs").addEventListener("click", (e) => {
            const t = e.target.closest(".tab"); if (t) openTab(t.dataset.tab);
        });

        $("formPengaturan").addEventListener("submit", async (e) => {
            e.preventDefault();
            const s = collect(), err = validate(s);
            if (err) {
                const el = $(err[0]); openTab(el.closest(".panel").id); el.focus();
                return SM.toast(err[1], "error");
            }
            if (s.notifBrowser && "Notification" in window && Notification.permission === "default") await Notification.requestPermission();
            SM.saveSettings(s);
            SM.api("/settings", { method: "POST", body: s });
            SM.toast("Pengaturan disimpan.", "success");
        });

        $("resetPengaturan").addEventListener("click", () => {
            if (!confirm("Kembalikan semua pengaturan ke nilai bawaan?")) return;
            fill(SM.defaults); SM.saveSettings(SM.defaults);
            SM.toast("Pengaturan dikembalikan ke bawaan.");
        });

        $("btnTest").addEventListener("click", async (e) => {
            const s = collect(), b = e.currentTarget; b.disabled = true; b.textContent = "Menguji...";
            const host = s.serverIP || location.hostname || "localhost";
            mark("st-server", await ping(`http://${host}:${s.apiPort || 5000}${s.apiPath || "/api"}/dashboard`));
            s.cameraIP ? mark("st-cam", await ping(`http://${s.cameraIP}`)) : mark("st-cam", false, true);
            s.controllerIP ? mark("st-ctl", await ping(`http://${s.controllerIP}`)) : mark("st-ctl", false, true);
            b.disabled = false; b.textContent = "Uji Koneksi";
        });
    });
})(window.SM);
