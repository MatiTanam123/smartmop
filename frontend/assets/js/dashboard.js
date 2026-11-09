/* Dashboard: menggunakan GET /dashboard, /detections, /logs, /devices/status */
(function (SM) {
  const $ = id => document.getElementById(id);
  const arr = v => Array.isArray(v) ? v : [];
  const number = v => v === null || v === undefined ? null : Number(v);
  const isSpill = name => !/(no[_ ]?spill|no[_ ]?spillage|clean|tidak ada|bersih)/i.test(String(name||""));
  function setLevel(valueId, barId, value, baseClass="") {
    const label=$(valueId), bar=$(barId);
    if (!label || !bar) return;
    const v=number(value);
    label.textContent = v === null || !Number.isFinite(v) ? "--" : `${Math.round(v)}%`;
    bar.style.width = v === null ? "0%" : `${Math.max(0,Math.min(100,v))}%`;
    bar.parentElement.className = "progress " + (v===null?"":v<15?"low":v<30?"warn":baseClass);
  }
  function deviceStatus(devices, code) {
    const d=arr(devices).find(x=>x.device_code===code);
    return d ? d.connection_status : "unknown";
  }
  function renderDetections(rows) {
    const target=$("detList"); if (!target) return;
    target.innerHTML = rows.length ? rows.slice(0,5).map(d=>{
      const spill=isSpill(d.class_name), conf=Math.round(Number(d.confidence||0)*100);
      return `<article class="det">
        ${SM.feed(spill?"spill":"clean","","thumb")}
        <div><h3 class="${spill?"bad":"good"}">${escapeHtml(d.class_name||"Deteksi")}</h3>
        <span class="pct ${spill?"bad":"good"}">${conf}%</span><time>${SM.formatTime(d.detected_at)}</time></div>
        <span class="badge ${spill?"danger":"success"}">${escapeHtml(d.decision_status||"accepted")}</span>
      </article>`;
    }).join("") : '<p class="empty">Belum ada data deteksi dari backend.</p>';
  }
  function renderLogs(rows) {
    const target=$("logList"); if (!target) return;
    target.innerHTML=rows.length ? rows.slice(0,6).map(l=>{
      const type=(l.severity==="error"||l.severity==="critical")?"danger":l.severity==="warning"?"warn":l.severity==="success"?"success":"info";
      return `<li class="${type}"><i></i><time>${SM.formatTime(l.created_at)}</time><span>${escapeHtml(l.message||l.event_type||"Aktivitas")}</span></li>`;
    }).join("") : '<li class="info"><i></i><span>Belum ada aktivitas tercatat.</span></li>';
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

  async function load() {
    try {
      const [dash, detections, logs, robotSettings] = await Promise.all([
        SM.getData("/dashboard"), SM.getData("/detections?limit=8"), SM.getData("/logs?limit=8"), SM.getData("/settings")
      ]);
      const devices=dash.devices||[];
      const controller=deviceStatus(devices,"ESP32_MAIN_01");
      const cam=deviceStatus(devices,"ESP32_CAM_01");
      const tele=dash.latest_telemetry||{};
      const online=controller==="online";
      if ($("statStatus")) $("statStatus").textContent=controller==="unknown"?"Belum diketahui":online?"Online":"Offline";
      if ($("statStatusSub")) $("statStatusSub").textContent=controller==="unknown"?"Menunggu heartbeat ESP32":online?"ESP32 controller mengirim heartbeat":"Heartbeat ESP32 tidak diterima dalam 60 detik";
      const modeLabel=robotSettings.operation_mode==="automatic"?"Otomatis":"Manual";
      if ($("statMode")) $("statMode").textContent=modeLabel;
      if ($("statModeSub")) $("statModeSub").textContent=`${dash.active_cleaning_sessions||0} sesi pembersihan aktif`;
      setLevel("soapValue","soapBar",tele.soap_level_percent);
      setLevel("batteryValue","batteryBar",tele.battery_percent,"green");
      if ($("soapValue") && $("soapBar") && tele.soap_level_percent==null) setLevel("soapValue","soapBar",null);
      renderDetections(arr(detections));
      renderLogs(arr(logs));
      SM.setOnline(online);
      const statusEvent=new CustomEvent("sm:dashboard",{detail:{dashboard:dash,devices,detections,logs,cameraOnline:cam==="online"}});
      document.dispatchEvent(statusEvent);
      SM.demo=false;
    } catch (err) {
      if ($("statStatus")) $("statStatus").textContent="API tidak tersedia";
      if ($("statStatusSub")) $("statStatusSub").textContent=err.message;
      SM.setOnline(false);
      const det=$("detList"); if(det) det.innerHTML='<p class="empty">Tidak dapat mengambil data. Periksa Flask dan alamat API di Pengaturan.</p>';
      const log=$("logList"); if(log) log.innerHTML='<li class="danger"><i></i><span>Gagal mengambil log dari backend.</span></li>';
    }
  }
  document.addEventListener("DOMContentLoaded",()=>{
    document.querySelectorAll(".stat-icon.tone-green").forEach((e,i)=>e.innerHTML=SM.icon(i?"battery":"robot"));
    const grey=document.querySelector(".stat-icon.tone-grey"); if(grey) grey.innerHTML=SM.icon("control");
    const blue=document.querySelector(".stat-icon.tone-blue"); if(blue) blue.innerHTML=SM.icon("drop");
    load(); setInterval(load,5000);
  });
  document.addEventListener("sm:log-local",load);
})(window.SM);
