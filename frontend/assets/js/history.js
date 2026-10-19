/* SMARTMOP - history.js : halaman Riwayat */
(function (SM) {
    const $ = (id) => document.getElementById(id);
    let rows = [];

    const BADGE = { "Dibersihkan": "success", "Gagal": "danger", "-": "neutral" };

    function draw() {
        const from = $("fFrom").value, to = $("fTo").value, st = $("fStatus").value;
        const list = rows.filter((r) => (!from || r.date >= from) && (!to || r.date <= to) && (!st || r.status === st));
        $("histBody").innerHTML = list.length ? list.map((r, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${r.date.split("-").reverse().join("/")}<br><small style="color:var(--text-secondary)">${r.time}</small></td>
                <td>${SM.feed(r.spill ? "spill" : "clean", "", "thumb")}</td>
                <td style="color:${r.spill ? "var(--danger)" : "var(--navy)"};font-weight:600">${r.label}</td>
                <td style="color:${r.spill ? "var(--danger)" : "var(--success)"};font-weight:700">${r.confidence}%</td>
                <td><span class="badge ${BADGE[r.status] || "neutral"}">${r.status === "-" ? "Tidak perlu" : r.status}</span></td>
            </tr>`).join("")
            : '<tr><td colspan="6" class="empty">Tidak ada data pada rentang ini. Ubah tanggal atau status lalu coba lagi.</td></tr>';
        $("histCount").textContent = `Menampilkan ${list.length} dari ${rows.length} catatan.`;
    }

    document.addEventListener("DOMContentLoaded", async () => {
        if (!$("filterForm")) return;
        $("btnFilter").innerHTML = SM.icon("filter") + "Filter";
        $("filterForm").addEventListener("submit", (e) => { e.preventDefault(); draw(); });
        $("btnReset").addEventListener("click", () => { $("filterForm").reset(); draw(); });
        rows = await SM.api("/history");
        draw();
    });
})(window.SM);
