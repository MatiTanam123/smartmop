/* SMARTMOP - notifications.js : lonceng notifikasi di topbar */
(function (SM) {
    document.addEventListener("DOMContentLoaded", () => {
        const bell = document.getElementById("bell");
        if (!bell) return;
        const s = SM.settings();
        let items = [
            { t: "Tumpahan terdeteksi (87%)", s: "Menunggu pembersihan" },
            { t: "Level sabun 68%", s: "Masih cukup" },
            { t: "Baterai 85%", s: "Kondisi baik" }
        ];
        const render = (open) => {
            const n = items.length;
            bell.innerHTML = `<button aria-label="Notifikasi, ${n} belum dibaca" aria-expanded="${!!open}">${SM.icon("bell")}
                ${n && s.notifWeb ? `<span class="bell-count">${n}</span>` : ""}</button>
                ${open ? `<ul class="bell-menu">${items.length ? items.map((i) => `<li><strong>${i.t}</strong><small>${i.s}</small></li>`).join("") : '<li><small>Tidak ada notifikasi baru.</small></li>'}
                ${items.length ? '<button id="readAll">Tandai semua dibaca</button>' : ""}</ul>` : ""}`;
            bell.firstElementChild.onclick = (e) => { e.stopPropagation(); render(!open); };
            bell.querySelector("#readAll")?.addEventListener("click", () => { items = []; render(true); });
        };
        document.addEventListener("click", (e) => { if (!bell.contains(e.target)) render(false); });
        render(false);

        // Notifikasi browser (hanya bila diizinkan di Pengaturan)
        document.addEventListener("sm:alert", (e) => {
            if (s.notifBrowser && "Notification" in window && Notification.permission === "granted") new Notification("SmartMop", { body: e.detail });
        });
    });
})(window.SM);
