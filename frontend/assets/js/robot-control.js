/* Kontrol robot memakai endpoint yang benar-benar tersedia pada Flask backend. */
(function(SM){
  const $=id=>document.getElementById(id);
  let mode="Otomatis", activeSession=null;
  const modeToDb=m=>m==="Otomatis"?"automatic":"manual";
  async function saveMode(m){
    await SM.api("/settings",{method:"PUT",body:{operation_mode:modeToDb(m)}});
    const s=SM.settings(); s.modeAwal=m; SM.saveSettings(s);
  }
  async function sendMove(direction){
    return SM.command("move",{direction},"ESP32_MAIN_01");
  }
  document.addEventListener("DOMContentLoaded",()=>{
    if(!$("modeSeg")) return;
    $("modeAuto").innerHTML=SM.icon("settings")+"Otomatis";
    $("modeManual").innerHTML=SM.icon("gamepad")+"Manual";
    ["up","left","stop","right","down"].forEach(k=>{const b=document.querySelector(`.dpad .${k}`);if(b)b.innerHTML=SM.icon(k);});
    $("btnStart").innerHTML=SM.icon("play")+"Mulai Mengepel";
    $("btnStop").innerHTML=SM.icon("stop")+"Berhenti";
    const setMode=m=>{
      mode=m;
      document.querySelectorAll("#modeSeg button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.mode===m)));
      if($("dpad")) $("dpad").dataset.disabled=String(m!=="Manual");
      document.dispatchEvent(new CustomEvent("sm:mode",{detail:m}));
    };
    setMode(SM.settings().modeAwal||"Otomatis");
    $("modeSeg").addEventListener("click",async e=>{
      const b=e.target.closest("button"); if(!b||!b.dataset.mode)return;
      const next=b.dataset.mode;
      try{await saveMode(next);setMode(next);SM.toast(`Mode ${next} tersimpan di database.`,"success");}
      catch(err){SM.toast(`Gagal mengubah mode: ${err.message}`,"error");}
    });
    $("dpad").addEventListener("click",async e=>{
      const b=e.target.closest("button"); if(!b)return;
      if(mode!=="Manual")return SM.toast("Pilih mode Manual terlebih dahulu.","warn");
      try{await sendMove(b.dataset.dir);SM.toast(`Perintah arah ${b.dataset.dir} masuk antrean.`,"success");}
      catch(err){SM.toast(`Perintah gagal: ${err.message}`,"error");}
    });
    $("btnStart").addEventListener("click",async()=>{
      try{
        const created=await SM.getData("/cleaning/start",{method:"POST",body:{operation_mode:modeToDb(mode),device_code:"ESP32_MAIN_01"}});
        activeSession=created.session_id;
        await SM.command("clean_start",{action:"start"},"ESP32_MAIN_01",activeSession);
        SM.toast("Sesi dibuat dan perintah dikirim ke antrean robot.","success");
        SM.addLog("Perintah mulai mengepel dikirim.");
      }catch(err){SM.toast(`Gagal memulai pembersihan: ${err.message}`,"error");}
    });
    $("btnStop").addEventListener("click",async()=>{
      try{
        await SM.command("clean_stop",{action:"stop"},"ESP32_MAIN_01",activeSession);
        if(activeSession) await SM.api(`/cleaning/${activeSession}/status`,{method:"PUT",body:{session_status:"cancelled",notes:"Dihentikan dari dashboard"}});
        activeSession=null; SM.toast("Perintah berhenti dikirim ke robot.","success");
      }catch(err){SM.toast(`Gagal menghentikan robot: ${err.message}`,"error");}
    });
    $("swPump")?.addEventListener("change",async e=>{
      try{await SM.command("pump_set",{on:e.target.checked});SM.toast("Perintah pompa dikirim.");}
      catch(err){e.target.checked=!e.target.checked;SM.toast(err.message,"error");}
    });
    $("swMotor")?.addEventListener("change",async e=>{
      try{await SM.command("mop_motor_set",{on:e.target.checked});SM.toast("Perintah motor pel dikirim.");}
      catch(err){e.target.checked=!e.target.checked;SM.toast(err.message,"error");}
    });
  });
})(window.SM);
