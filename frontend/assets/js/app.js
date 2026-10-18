const pad = (n) => String(n).padStart(2, '0');
function tick(){
    const now = new Date();
    const date = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
    const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    document.getElementById('clockDate').textContent = date;
    document.getElementById('clockTime').textContent = time;
};

setInterval(tick, 1000);
tick();