/* Pengaturan: sinkronisasi form lama ke tiga tabel settings backend. */
(function(SM){
 const $=id=>document.getElementById(id);
 const fields=()=>document.querySelectorAll("[data-setting]");
 const modeFromDb=v=>v==="manual"?"Manual":"Otomatis";
 const speedFromDb=v=>({slow:"Pelan",medium:"Sedang",fast:"Cepat"}[v]||"Sedang");
 const soapFromDb=v=>({low:"Rendah",medium:"Sedang",high:"Tinggi"}[v]||"Sedang");
 function fill(s){fields().forEach(el=>{if(el.type==="checkbox")el.checked=!!s[el.id];else el.value=s[el.id]??"";});}
 function collect(){const s=Object.assign({},SM.settings());fields().forEach(el=>s[el.id]=el.type==="checkbox"?el.checked:el.value.trim());return s;}
 function openTab(name){document.querySelectorAll(".tab").forEach(t=>t.setAttribute("aria-selected",String(t.dataset.tab===name)));document.querySelectorAll(".panel").forEach(p=>p.hidden=p.id!==name);history.replaceState(null,"","#"+name);}
 function valid(s){
  const c=Number(s.confidence);if(!Number.isFinite(c)||c<0||c>1)return["confidence","Confidence harus 0 sampai 1."];
  const port=Number(s.apiPort);if(!Number.isInteger(port)||port<1||port>65535)return["apiPort","Port API harus 1 sampai 65535."];
  for(const k of ["serverIP","cameraIP","controllerIP"])if(s[k]&&!/^(\d{1,3}\.){3}\d{1,3}$/.test(s[k])&&s[k]!=="localhost")return[k,"Format IP tidak valid."];
  return null;
 }
 async function loadSettings(){
  try{
   const [r,a,n]=await Promise.all([SM.getData("/settings"),SM.getData("/app-settings"),SM.getData("/notifications/settings")]);
   const s=Object.assign({},SM.defaults,{
    namaRobot:r.robot_name,modeAwal:modeFromDb(r.operation_mode),kecepatan:speedFromDb(r.movement_speed),
    waktuPemotretan:String(r.camera_interval_seconds),confidence:String(r.confidence_threshold),
    pengulangan:String(r.cleaning_repeats),volumeSabun:soapFromDb(r.soap_volume_preset),
    ukuranModel:String(a.image_size),bbox:a.show_bbox,simpanGambar:a.save_detection_images,
    batasBaterai:String(a.low_battery_threshold),batasSabun:String(a.low_soap_threshold),stopBaterai:a.stop_on_low_battery,
    ssid:a.wifi_ssid||"",serverIP:a.server_host||"",apiPort:String(a.api_port),apiPath:a.api_prefix||"/api",
    cameraIP:a.camera_ip||"",controllerIP:a.controller_ip||"",
    notifWeb:n.website_notification,notifSuara:n.sound_notification,notifBrowser:n.browser_notification,
    notifSelesai:n.cleaning_completed,notifError:n.system_error
   });
   SM.saveSettings(s);fill(s);
  }catch(err){fill(SM.settings());SM.toast("Pengaturan database belum dapat dimuat: "+err.message,"warn");}
 }
 async function saveSettings(s){
  const robot={
   robot_name:s.namaRobot,operation_mode:s.modeAwal==="Manual"?"manual":"automatic",
   camera_interval_seconds:Number(s.waktuPemotretan),confidence_threshold:Number(s.confidence),
   movement_speed:({Pelan:"slow",Sedang:"medium",Cepat:"fast"}[s.kecepatan]||"medium"),
   cleaning_repeats:Number(s.pengulangan),soap_volume_preset:({Rendah:"low",Sedang:"medium",Tinggi:"high"}[s.volumeSabun]||"medium")
  };
  const app={
   image_size:Number(s.ukuranModel),show_bbox:s.bbox,save_detection_images:s.simpanGambar,
   low_battery_threshold:Number(s.batasBaterai),low_soap_threshold:Number(s.batasSabun),
   stop_on_low_battery:s.stopBaterai,wifi_ssid:s.ssid||null,server_host:s.serverIP||null,
   api_port:Number(s.apiPort),api_prefix:s.apiPath||"/api",camera_ip:s.cameraIP||null,controller_ip:s.controllerIP||null
  };
  const notif={website_notification:s.notifWeb,sound_notification:s.notifSuara,browser_notification:s.notifBrowser,cleaning_completed:s.notifSelesai,system_error:s.notifError};
  await Promise.all([
   SM.api("/settings",{method:"PUT",body:robot}),
   SM.api("/app-settings",{method:"PUT",body:app}),
   SM.api("/notifications/settings",{method:"PUT",body:notif})
  ]);
  SM.saveSettings(s);
 }
 async function testConnection(){
  const host=$("serverIP").value.trim()||location.hostname||"127.0.0.1";
  const port=$("apiPort").value||"5000",prefix=$("apiPath").value||"/api";
  const url=`http://${host}:${port}${prefix.replace(/\/+$/,"")}/health`;
  const set=(id,ok,empty=false)=>{const e=$(id);if(!e)return;e.className="connection-indicator "+(empty?"":ok?"ok":"fail");e.textContent=empty?"IP belum diisi":ok?"Terhubung":"Tidak terjangkau";};
  try{const r=await fetch(url,{cache:"no-store"});set("st-server",r.ok);}
  catch(_){set("st-server",false);}
  const ping=async ip=>{if(!ip)return null;try{const c=new AbortController(),t=setTimeout(()=>c.abort(),2500);await fetch(`http://${ip}`,{mode:"no-cors",signal:c.signal});clearTimeout(t);return true;}catch(_){return false;}};
  const [cam,ctl]=await Promise.all([ping($("cameraIP").value.trim()),ping($("controllerIP").value.trim())]);
  set("st-cam",!!cam,cam===null);set("st-ctl",!!ctl,ctl===null);
 }
 document.addEventListener("DOMContentLoaded",()=>{
  if(!$("formPengaturan"))return;
  document.querySelectorAll("[data-icon]").forEach(e=>e.innerHTML=SM.icon(e.dataset.icon));
  $("simpanPengaturan").innerHTML=SM.icon("save")+"Simpan Pengaturan";
  loadSettings();
  const initial=location.hash.slice(1);if($(initial)?.classList.contains("panel"))openTab(initial);
  document.querySelector(".tabs")?.addEventListener("click",e=>{const t=e.target.closest(".tab");if(t)openTab(t.dataset.tab);});
  $("formPengaturan").addEventListener("submit",async e=>{
   e.preventDefault();const s=collect(),err=valid(s);
   if(err){const el=$(err[0]);if(el)openTab(el.closest(".panel").id);SM.toast(err[1],"error");return;}
   try{if(s.notifBrowser&&"Notification"in window&&Notification.permission==="default")await Notification.requestPermission();await saveSettings(s);SM.toast("Pengaturan berhasil disimpan ke Supabase.","success");}
   catch(error){SM.toast("Gagal menyimpan pengaturan: "+error.message,"error");}
  });
  $("resetPengaturan").addEventListener("click",async()=>{
   if(!confirm("Kembalikan pengaturan ke nilai bawaan dan simpan ke database?"))return;
   fill(SM.defaults);try{await saveSettings(SM.defaults);SM.toast("Pengaturan bawaan berhasil disimpan.");}catch(e){SM.toast(e.message,"error");}
  });
  $("btnTest").addEventListener("click",async e=>{e.preventDefault();e.currentTarget.disabled=true;e.currentTarget.textContent="Menguji...";await testConnection();e.currentTarget.disabled=false;e.currentTarget.textContent="Uji Koneksi";});
 });
})(window.SM);
