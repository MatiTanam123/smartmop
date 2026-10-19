/* SMARTMOP - dashboard.js : data Beranda (status, deteksi, log) */
(function (SM) {
    const $ = (id) => document.getElementById(id);
    let seeded = false;

    function level(bar, v, base) {
        bar.style.width = v + "%";
        bar.parentElement.className = "progress " + (v < 15 ? "low" : v < 30 ? "warn" : base);
    }

    function render(d) {
        const r = d.robot;
        $("statStatus").textContent = r.status;
        $("soapValue").textContent = r.soap + "%";
        $("batteryValue").textContent = r.battery + "%";
        level($("soapBar"), r.soap, "");
        level($("batteryBar"), r.battery, "green");
        if (!SM.modeChanged) setMode(r.mode);

        $("detList").innerHTML = d.detections.map((x) => `
            <article class="det">
                ${SM.feed(x.spill ? "spill" : "clean", "", "sm")}
                <div>
                    <h3 class="${x.spill ? "bad" : "good"}">${x.label}</h3>
                    <span class="pct ${x.spill ? "bad" : "good"}">${x.confidence}%</span>
                    <time>${x.time}</time>
                </div>
                <span class="badge ${x.spill ? "danger" : "success"}">${x.status}</span>
            </article>`).join("");

        if (!seeded) { seeded = true; SM.log = d.log.slice(); drawLog(); }
    }

    function setMode(m) {
        $("statMode").textContent = m;
        $("statModeSub").textContent = m === "Otomatis" ? "Menunggu deteksi tumpahan" : "Dikendalikan secara manual";
    }

    function drawLog() {
        $("logList").innerHTML = SM.log.slice(0, 6).map((l) =>
            `<li class="${l.type}"><i></i><time>${l.time}</time><span>${l.text}</span></li>`).join("");
    }

    async function load() { render(await SM.api("/dashboard")); }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelector(".stat-icon.tone-green").innerHTML = SM.icon("robot");
        document.querySelector(".stat-icon.tone-grey").innerHTML = SM.icon("control");
        document.querySelector(".stat-icon.tone-blue").innerHTML = SM.icon("drop");
        document.querySelectorAll(".stat-icon.tone-green")[1].innerHTML = SM.icon("battery");
        load();
        setInterval(load, 5000);
    });
    document.addEventListener("sm:log", drawLog);
    document.addEventListener("sm:mode", (e) => { SM.modeChanged = true; setMode(e.detail); });
})(window.SM);
