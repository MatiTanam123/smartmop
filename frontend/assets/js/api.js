/* SmartMop API client - diselaraskan dengan Flask backend */
window.SM = window.SM || {};
(function (SM) {
  const KEY = "smartmop.settings";
  SM.defaults = {
    namaRobot:"SmartMop-01", modeAwal:"Otomatis", kecepatan:"Sedang",
    waktuPemotretan:"3", confidence:"0.65", pengulangan:"2", volumeSabun:"Sedang",
    ukuranModel:"640", bbox:true, simpanGambar:true, batasBaterai:"20",
    batasSabun:"15", stopBaterai:true, notifWeb:true, notifSuara:true,
    notifBrowser:false, notifSelesai:true, notifError:true,
    ssid:"", serverIP:"", apiPort:"5000", apiPath:"/api", cameraIP:"", controllerIP:""
  };

  SM.settings = () => {
    try { return Object.assign({}, SM.defaults, JSON.parse(localStorage.getItem(KEY) || "{}")); }
    catch (_) { return Object.assign({}, SM.defaults); }
  };
  SM.saveSettings = (s) => localStorage.setItem(KEY, JSON.stringify(s));
  SM.apiBase = () => {
    const s = SM.settings();
    const host = (s.serverIP || location.hostname || "127.0.0.1").trim();
    const port = s.apiPort || "5000";
    const prefix = (s.apiPath || "/api").replace(/\/+$/, "");
    return `http://${host}:${port}${prefix}`;
  };
  SM.unwrap = (payload) => payload && Object.prototype.hasOwnProperty.call(payload, "data") ? payload.data : payload;

  SM.api = async (path, opt = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), opt.timeout || 8000);
    let response;
    try {
      response = await fetch(SM.apiBase() + path, {
        method: opt.method || "GET",
        headers: Object.assign({ "Accept":"application/json" }, opt.body ? {"Content-Type":"application/json"} : {}, opt.headers || {}),
        body: opt.body === undefined ? undefined : JSON.stringify(opt.body),
        signal: controller.signal,
        cache: "no-store"
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.success === false) {
        const err = new Error(payload.message || `HTTP ${response.status}`);
        err.status = response.status; err.payload = payload; throw err;
      }
      SM.demo = false;
      SM.lastApiError = null;
      return payload;
    } catch (err) {
      SM.demo = true;
      SM.lastApiError = err;
      throw err;
    } finally { clearTimeout(timeout); }
  };
  SM.getData = async (path, opt) => SM.unwrap(await SM.api(path, opt));
  SM.command = (command_type, command_payload = {}, device_code = "ESP32_MAIN_01", session_id = null) =>
    SM.getData("/commands", {method:"POST", body:{device_code, session_id, command_type, command_payload}});

  const pad = n => String(n).padStart(2,"0");
  SM.formatTime = value => {
    if (!value) return "--:--:--";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleTimeString("id-ID");
  };
  SM.formatDate = value => {
    if (!value) return "-";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString("id-ID");
  };
  SM.toast = (message, type="") => {
    let box = document.getElementById("toasts");
    if (!box) { box=document.createElement("div"); box.id="toasts"; box.className="toasts"; document.body.appendChild(box); }
    const item=document.createElement("div"); item.className=`toast ${type}`; item.textContent=message; box.appendChild(item);
    setTimeout(()=>item.remove(),4500);
  };
  SM.addLog = (message, type="info") => {
    document.dispatchEvent(new CustomEvent("sm:log-local",{detail:{message,type,created_at:new Date().toISOString()}}));
  };
  SM.setOnline = on => {
    const el=document.getElementById("onlineState");
    if (!el) return;
    el.classList.toggle("off",!on);
    if (el.lastElementChild) el.lastElementChild.textContent=on?"Online":"Offline";
  };
  SM.icon = SM.icon || (name => name);
  SM.feed = (kind, label="", size="") => `<div class="feed ${kind==="mop"?"mop":""} ${size}">${kind==="spill"?'<span class="spill"></span><span class="bbox"></span>':kind==="mop"?'<span class="pad"></span><span class="pad"></span>':""}</div>`;
})(window.SM);
