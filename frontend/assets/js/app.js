/* SMARTMOP - app.js
   Kerangka halaman bersama: sidebar, topbar, jam, toast, tampilan kamera simulasi. */
window.SM = window.SM || {};
(function (SM) {
    const P = {
        home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
        camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="3.5"/>',
        history: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
        control: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
        settings: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
        bell: '<path d="M6 16v-5a6 6 0 0112 0v5l2 2H4z"/><path d="M10 21h4"/>',
        drop: '<path d="M12 3s6 6.5 6 11a6 6 0 01-12 0c0-4.5 6-11 6-11z"/>',
        battery: '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 11v2M7 10v4M11 10v4"/>',
        robot: '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V5"/><circle cx="12" cy="4" r="1"/><circle cx="9" cy="14" r="1.2"/><circle cx="15" cy="14" r="1.2"/>',
        power: '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1011.4 0"/>',
        stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
        play: '<path d="M7 4l13 8-13 8z"/>',
        up: '<path d="M6 15l6-6 6 6"/>', down: '<path d="M6 9l6 6 6-6"/>',
        left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>',
        gamepad: '<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 10v5M4.5 12.5h5"/><circle cx="16" cy="11.5" r="1"/><circle cx="18.5" cy="14" r="1"/>',
        mop: '<path d="M14 3l7 7-4 2-5-5z"/><path d="M12 7l-8 8c-1 3 0 6 0 6s4 0 6-1l8-8"/>',
        expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
        video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/>',
        save: '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/>',
        server: '<rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
        chip: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
        menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
        filter: '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>'
    };
    SM.icon = (n, c = "") => `<svg class="ico ${c}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;

    const NAV = [
        ["beranda", "Beranda", "home", "index.html"],
        ["live-camera", "Live Camera", "camera", "pages/live-camera.html"],
        ["riwayat", "Riwayat", "history", "pages/riwayat.html"],
        ["kontrol-robot", "Kontrol Robot", "control", "index.html#kontrol"],
        ["pengaturan", "Pengaturan", "settings", "pages/pengaturan.html"],
        ["status-sistem", "Status Sistem", "clock", "pages/status-sistem.html"],
        ["tentang", "Tentang", "info", "pages/tentang.html"]
    ];
    const $ = (id) => document.getElementById(id);
    const pad = (n) => String(n).padStart(2, "0");

    SM.toast = (msg, type = "") => {
        let box = $("toasts");
        if (!box) { box = document.createElement("div"); box.id = "toasts"; box.className = "toasts"; box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
        const t = document.createElement("div");
        t.className = "toast " + type; t.textContent = msg; box.appendChild(t);
        setTimeout(() => t.remove(), 4000);
    };

    /* Log aktivitas bersama (dipakai Beranda & halaman lain) */
    SM.log = [];
    SM.addLog = (text, type = "info") => {
        const d = new Date();
        SM.log.unshift({ time: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`, text, type });
        SM.log.length = Math.min(SM.log.length, 30);
        document.dispatchEvent(new CustomEvent("sm:log"));
    };

    /* Tampilan kamera simulasi: <div data-feed="spill|clean|mop" data-label="..." data-size="sm|thumb" data-stamp> */
    SM.feed = (kind, label, size, stamp) => {
        const inner = kind === "mop" ? '<span class="pad"></span><span class="pad"></span>'
            : kind === "spill" ? `<span class="spill"></span><span class="bbox">${label ? `<em>${label}</em>` : ""}</span>` : "";
        return `<div class="feed ${kind === "mop" ? "mop" : ""} ${size || ""}">${inner}${stamp ? '<time class="feed-time" data-stamp></time>' : ""}</div>`;
    };
    SM.hydrateFeeds = (root = document) => root.querySelectorAll("[data-feed]").forEach((el) => {
        const holder = document.createElement("div");
        holder.innerHTML = SM.feed(el.dataset.feed, el.dataset.label, el.dataset.size, "stamp" in el.dataset);
        const feed = holder.firstElementChild;
        el.replaceWith(feed);
        if (el.id) feed.id = el.id;
    });

    SM.setOnline = (on) => {
        const o = $("onlineState"); if (!o) return;
        o.classList.toggle("off", !on);
        o.lastElementChild.textContent = on ? "Online" : "Berhenti";
    };

    function shell() {
        const b = document.body, root = b.dataset.root || "", page = b.dataset.page;
        const sb = $("sidebar"), tb = $("topbar");
        if (sb) {
            sb.innerHTML = `<div class="brand"><span class="brand-mark">${SM.icon("robot")}</span>
                <div><strong>SmartMop</strong><small>AI Floor Cleaning Robot</small></div></div>
                <nav class="nav" aria-label="Menu utama">${NAV.map((n) =>
                    `<a href="${root}${n[3]}" ${n[0] === page ? 'aria-current="page"' : ""}>${SM.icon(n[2])}<span>${n[1]}</span></a>`).join("")}</nav>`;
        }
        if (tb) {
            tb.innerHTML = `<div class="topbar-title">
                <button class="menu-btn" id="menuBtn" aria-label="Buka menu">${SM.icon("menu")}</button>
                <div><h1>${b.dataset.title || "SmartMop"}</h1><p>${b.dataset.sub || ""}</p></div></div>
                <div class="top-actions">
                    <div class="bell" id="bell"></div>
                    <div class="clock"><small id="clockDate"></small><strong id="clockTime"></strong></div>
                    <div class="online" id="onlineState"><span class="dot"></span><span>Online</span></div>
                    <button class="btn-emergency" id="btnEmergency">${SM.icon("power")}HENTI DARURAT</button>
                </div>`;
        }
        const scrim = document.createElement("div"); scrim.className = "scrim"; document.body.appendChild(scrim);
        const toggle = (open) => { sb.classList.toggle("open", open); scrim.classList.toggle("show", open); };
        $("menuBtn")?.addEventListener("click", () => toggle(true));
        scrim.addEventListener("click", () => toggle(false));

        $("btnEmergency")?.addEventListener("click", async () => {
            if (!confirm("Hentikan semua motor dan pompa robot sekarang?")) return;
            await SM.api("/robot/emergency-stop", { method: "POST" });
            SM.setOnline(false);
            SM.addLog("Henti darurat diaktifkan", "danger");
            SM.toast("Henti darurat aktif. Robot dihentikan.", "error");
        });
    }

    function tick() {
        const d = new Date();
        const date = d.toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
        const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
        if ($("clockDate")) { $("clockDate").textContent = date; $("clockTime").textContent = time; }
        const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${time}`;
        document.querySelectorAll("[data-stamp]").forEach((e) => (e.textContent = stamp));
    }

    document.addEventListener("DOMContentLoaded", () => {
        shell(); SM.hydrateFeeds(); tick(); setInterval(tick, 1000);
    });
})(window.SM);
