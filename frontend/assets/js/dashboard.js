/* Bagian Waktu */

const pad = (n) => String(n).padStart(2, "0");
function tick() {
    const d = new Date();
    document.getElementById("clockDate").textContent =
        d.toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    document.getElementById("clockTime").textContent =
        `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
tick();
setInterval(tick, 1000);