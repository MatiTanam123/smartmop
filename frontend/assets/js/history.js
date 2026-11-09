/* Riwayat menggabungkan data detections dan cleaning_sessions dari backend. */
(function(SM){
 const $=id=>document.getElementById(id); let rows=[];
 const statusLabel=s=>({completed:"Dibersihkan",failed:"Gagal",cancelled:"Dibatalkan",pending:"Menunggu",approaching:"Menuju lokasi",mopping:"Mengepel",verifying:"Verifikasi"}[s]||s||"-");
 function draw(){
  const from=$("fFrom").value,to=$("fTo").value,st=$("fStatus").value;
  const list=rows.filter(r=>(!from||r.date>=from)&&(!to||r.date<=to)&&(!st||r.status===st));
  $("histBody").innerHTML=list.length?list.map((r,i)=>`<tr><td>${i+1}</td><td>${SM.formatDate(r.created_at)}<br><small>${SM.formatTime(r.created_at)}</small></td><td>${SM.feed(r.spill?"spill":"clean","","thumb")}</td><td>${escapeHtml(r.label)}</td><td>${r.confidence==null?"-":Math.round(r.confidence*100)+"%"}</td><td><span class="badge ${r.status==="Dibersihkan"?"success":r.status==="Gagal"?"danger":"neutral"}">${escapeHtml(r.status)}</span></td></tr>`).join(""):'<tr><td colspan="6" class="empty">Belum ada riwayat sesuai filter.</td></tr>';
  $("histCount").textContent=`Menampilkan ${list.length} dari ${rows.length} catatan.`;
 }
 function escapeHtml(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
 async function load(){
  try{
   const [detections,sessions]=await Promise.all([SM.getData("/detections?limit=200"),SM.getData("/cleaning/history")]);
   const byDetection=new Map((sessions||[]).map(s=>[String(s.detection_id),s]));
   rows=(detections||[]).map(d=>{
    const session=byDetection.get(String(d.detection_id));
    const spill=!/(no[_ ]?spill|clean|tidak ada|bersih)/i.test(d.class_name||"");
    return {created_at:d.detected_at,date:d.detected_at?new Date(d.detected_at).toISOString().slice(0,10):"",label:d.class_name,spill,confidence:Number(d.confidence),status:session?statusLabel(session.session_status):(spill?"Belum dibersihkan":"-")};
   });
   (sessions||[]).filter(s=>!s.detection_id).forEach(s=>rows.push({created_at:s.started_at||s.created_at,date:(s.started_at||s.created_at||"").slice(0,10),label:"Pembersihan manual",spill:false,confidence:null,status:statusLabel(s.session_status)}));
   rows.sort((a,b)=>new Date(b.created_at)-new Date(a.created_at)); draw();
  }catch(err){$("histBody").innerHTML=`<tr><td colspan="6" class="empty">Gagal mengambil riwayat: ${escapeHtml(err.message)}</td></tr>`;$("histCount").textContent="Backend tidak dapat diakses.";}
 }
 document.addEventListener("DOMContentLoaded",()=>{
  if(!$("filterForm"))return;
  $("btnFilter").innerHTML=SM.icon("filter")+"Filter";
  $("filterForm").addEventListener("submit",e=>{e.preventDefault();draw();});
  $("btnReset").addEventListener("click",()=>{$("filterForm").reset();draw();});
  load();
 });
})(window.SM);
