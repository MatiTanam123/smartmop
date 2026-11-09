/* Status sistem menggunakan /health, /devices/status, dan /logs. */
(function(SM){
 const $=id=>document.getElementById(id);
 function state(id,online,text){const e=$(id);if(!e)return;e.textContent=text;e.classList.remove("sm-online","sm-offline","sm-unknown");e.classList.add(online===true?"sm-online":online===false?"sm-offline":"sm-unknown");}
 function log(message){const box=$("systemLogs");if(!box)return;const empty=box.querySelector(".sm-muted");if(empty)empty.remove();const row=document.createElement("div");row.className="sm-log-item";const a=document.createElement("span");a.textContent=message;const b=document.createElement("span");b.className="sm-log-time";b.textContent=new Date().toLocaleTimeString("id-ID");row.append(a,b);box.prepend(row);}
 async function check(){
  $("refreshStatus").disabled=true;$("refreshStatus").textContent="Memeriksa...";
  state("apiState",null,"Memeriksa...");
  try{
   await SM.api("/health");state("apiState",true,"Terhubung");$("apiNote").textContent="Flask API merespons.";
   const [devices,logs]=await Promise.all([SM.getData("/devices/status"),SM.getData("/logs?limit=30")]);
   const cam=(devices||[]).find(d=>d.device_code==="ESP32_CAM_01"),ctl=(devices||[]).find(d=>d.device_code==="ESP32_MAIN_01");
   const online=d=>d?.connection_status==="online";
   state("robotState",ctl?online(ctl):null,ctl?(online(ctl)?"Online":ctl.connection_status==="offline"?"Offline":"Belum ada heartbeat"):"Tidak terdaftar");
   $("robotNote").textContent=ctl?.last_seen_at?`Heartbeat terakhir: ${SM.formatDate(ctl.last_seen_at)} ${SM.formatTime(ctl.last_seen_at)}`:"ESP32 belum mengirim heartbeat.";
   state("camState",cam?online(cam):null,cam?(online(cam)?"Online":cam.connection_status==="offline"?"Offline":"Belum ada heartbeat"):"Tidak terdaftar");
   $("camNote").textContent=cam?.last_seen_at?`Heartbeat terakhir: ${SM.formatTime(cam.last_seen_at)}`:"Kamera belum mengirim heartbeat.";
   state("controllerState",ctl?online(ctl):null,ctl?(online(ctl)?"Online":ctl.connection_status==="offline"?"Offline":"Belum ada heartbeat"):"Tidak terdaftar");
   $("controllerNote").textContent=ctl?.ip_address||"Alamat IP belum dilaporkan.";
   $("systemLogs").innerHTML=(logs||[]).length?(logs||[]).map(l=>`<div class="sm-log-item"><span>${escapeHtml(l.message||l.event_type)}</span><span class="sm-log-time">${SM.formatTime(l.created_at)}</span></div>`).join(""):'<p class="sm-muted">Belum ada aktivitas dari database.</p>';
   log("Pemeriksaan status berhasil.");
  }catch(err){state("apiState",false,"Tidak terhubung");$("apiNote").textContent=err.message;state("robotState",null,"Tidak diketahui");state("camState",null,"Tidak diketahui");state("controllerState",null,"Tidak diketahui");log("Gagal memeriksa backend: "+err.message);}
  $("apiAddress").textContent="Alamat backend: "+SM.apiBase();
  $("refreshStatus").disabled=false;$("refreshStatus").textContent="Periksa Koneksi";
 }
 function escapeHtml(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
 document.addEventListener("DOMContentLoaded",()=>{if(!$("refreshStatus"))return;$("refreshStatus").addEventListener("click",check);$("clearLogs").addEventListener("click",()=>$("systemLogs").innerHTML='<p class="sm-muted">Log tampilan dibersihkan. Data database tidak dihapus.</p>');check();setInterval(check,10000);});
})(window.SM);
