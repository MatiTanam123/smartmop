/* SMARTMOP - robot-control.js : mode, arah, mulai/berhenti, pompa & motor */
(function (SM) {
    const $ = (id) => document.getElementById(id);
    let mode = "Otomatis", cleaning = false;

    function setMode(m) {
        mode = m;
        document.querySelectorAll("#modeSeg button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === m));
        $("dpad").dataset.disabled = m === "Otomatis";
        document.dispatchEvent(new CustomEvent("sm:mode", { detail: m }));
    }

    async function send(path, body, okMsg) {
        const r = await SM.api(path, { method: "POST", body });
        if (okMsg) SM.addLog(okMsg, "info");
        return r;
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (!$("modeSeg")) return;
        $("modeAuto").innerHTML = SM.icon("settings") + "Otomatis";
        $("modeManual").innerHTML = SM.icon("gamepad") + "Manual";
        const arrows = { up: "up", left: "left", stop: "stop", right: "right", down: "down" };
        Object.keys(arrows).forEach((k) => (document.querySelector(`.dpad .${k}`).innerHTML = SM.icon(arrows[k])));
        $("btnStart").innerHTML = SM.icon("play") + "Mulai Mengepel";
        $("btnStop").innerHTML = SM.icon("stop") + "Berhenti";
        $("icoPump").innerHTML = SM.icon("drop") + "Pompa Sabun";
        $("icoMotor").innerHTML = SM.icon("mop") + "Motor Pel";

        setMode(SM.settings().modeAwal || "Otomatis");

        $("modeSeg").addEventListener("click", (e) => {
            const b = e.target.closest("button"); if (!b || b.dataset.mode === mode) return;
            setMode(b.dataset.mode);
            send("/robot/mode", { mode: b.dataset.mode }, `Mode ${b.dataset.mode} diaktifkan`);
        });

        $("dpad").addEventListener("click", (e) => {
            const b = e.target.closest("button"); if (!b) return;
            if (mode !== "Manual") return SM.toast("Pindah ke mode Manual untuk menggerakkan robot.", "warn");
            send("/robot/move", { direction: b.dataset.dir }, `Robot: ${b.dataset.dir}`);
        });

        $("btnStart").addEventListener("click", () => {
            if (cleaning) return SM.toast("Proses mengepel sedang berjalan.");
            cleaning = true;
            send("/robot/clean", { action: "start" }, "Proses mengepel dimulai");
            SM.toast("Proses mengepel dimulai.", "success");
        });
        $("btnStop").addEventListener("click", () => {
            cleaning = false;
            send("/robot/clean", { action: "stop" }, "Proses mengepel dihentikan");
            SM.toast("Proses mengepel dihentikan.");
        });

        $("swPump").addEventListener("change", (e) => send("/robot/pump", { on: e.target.checked }, `Pompa sabun ${e.target.checked ? "menyala" : "mati"}`));
        $("swMotor").addEventListener("change", (e) => send("/robot/motor", { on: e.target.checked }, `Motor pel ${e.target.checked ? "menyala" : "mati"}`));
    });
})(window.SM);
