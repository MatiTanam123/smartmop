/* Live camera: stream langsung ESP32-CAM; kualitas dikirim sebagai command antrean backend. */
(function(SM){
 const $=id=>document.getElementById(id);
 document.addEventListener("DOMContentLoaded",()=>{
  const feed=$("mainFeed");if(!feed)return;
  $("icoPhoto").innerHTML=SM.icon("camera");$("icoRec").innerHTML=SM.icon("video");$("icoFull").innerHTML=SM.icon("expand");
  const ip=SM.settings().cameraIP;let img=null;
  if(ip){
   img=new Image();img.className="stream";img.alt="Live stream ESP32-CAM";
   img.onload=()=>$("camInfo").textContent=`Stream ESP32-CAM aktif di ${ip}.`;
   img.onerror=()=>$("camInfo").textContent=`Stream ${ip}:81 tidak dapat diakses. Periksa IP, Wi-Fi, dan endpoint stream kamera.`;
   img.src=`http://${ip}:81/stream`;feed.prepend(img);
  }else $("camInfo").textContent="Isi IP ESP32-CAM pada Pengaturan > Jaringan untuk menampilkan stream.";
  $("btnPhoto").addEventListener("click",()=>{
   if(!img||!img.complete||!img.naturalWidth)return SM.toast("Stream kamera belum tersedia.","warn");
   try{const c=document.createElement("canvas");c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext("2d").drawImage(img,0,0);const a=document.createElement("a");a.href=c.toDataURL("image/jpeg",.92);a.download=`smartmop-${Date.now()}.jpg`;a.click();}catch(_){SM.toast("Browser menolak mengambil gambar dari stream lintas-origin. Coba simpan dari kamera/server.","warn");}
  });
  let rec=null,sec=0;const pad=n=>String(n).padStart(2,"0");
  $("btnRec").addEventListener("click",e=>{const on=!rec;e.currentTarget.setAttribute("aria-pressed",String(on));if(on){sec=0;rec=setInterval(()=>{sec++;$("recLabel").textContent=`${pad(Math.floor(sec/60))}:${pad(sec%60)}`;},1000);$("recLabel").textContent="00:00";}else{clearInterval(rec);rec=null;$("recLabel").textContent="Rekam";}});
  $("btnHD").addEventListener("click",async e=>{const quality=e.currentTarget.getAttribute("aria-pressed")==="true"?"HD":"SD";try{await SM.command("camera_quality",{quality},"ESP32_CAM_01");e.currentTarget.setAttribute("aria-pressed",String(quality==="SD"));$("hdTag").textContent=quality;SM.toast(`Perintah kualitas ${quality} dikirim ke kamera.`);}catch(err){SM.toast("Gagal mengirim perintah: "+err.message,"error");}});
  $("btnFull").addEventListener("click",()=>document.fullscreenElement?document.exitFullscreen():feed.requestFullscreen?.());
 });
})(window.SM);
