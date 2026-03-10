function safeGet(id) {
    return document.getElementById(id);
}

function safeSetText(id, text) {
    const el = safeGet(id);
    if (el) el.textContent = text;
}

function safeShow(id, display = "block") {
    const el = safeGet(id);
    if (el) el.style.display = display;
}
// ─────────────────────────────────────────────────────────
// QWebChannel Setup
// ─────────────────────────────────────────────────────────
var bridge = null;

function setupBridge(){

    new QWebChannel(qt.webChannelTransport, function(channel){

        bridge = channel.objects.bridge;

        console.log("Bridge Connected =", bridge);

        bridge.trainingFinished.connect(function(message){
            showToast(message,4000);
            addLog(message);
        });

        bridge.trainingStatus.connect(function(message){
            addLog(message);
        });

        bridge.frameUpdate.connect(function(base64Frame){

            const video = document.getElementById("videoFeed");
            const noFeed = document.getElementById("noFeed");

            if(video && base64Frame){

                video.style.display = "block";
                video.src = base64Frame;

            }

            if(noFeed){
                noFeed.style.display = "none";
            }

        });

    });

}

// ⭐ Wait for DOM + Qt channel ready
window.onload = function(){
    setTimeout(setupBridge, 500);
};


// ─────────────────────────────────────────────────────────
// Clock
// ─────────────────────────────────────────────────────────
function updateClockSafe() {

    const clock = document.getElementById("clock");

    if (!clock) return;

    clock.textContent =
        new Date().toTimeString().slice(0, 8);
}

setInterval(updateClockSafe, 1000);
updateClockSafe();

// ─────────────────────────────────────────────────────────
// Uptime
// ─────────────────────────────────────────────────────────
let sessionStart = null;
let uptimeTimer = null;

window.startUptime = function () {

    sessionStart = Date.now();

    if (uptimeTimer) clearInterval(uptimeTimer);

    uptimeTimer = setInterval(() => {

        const el = document.getElementById("uptimeVal");
        if (!el) return;

        const s = Math.floor((Date.now() - sessionStart) / 1000);

        el.textContent =
            `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

    }, 1000);
};

window.stopUptime = function () {

    if (uptimeTimer) {
        clearInterval(uptimeTimer);
        uptimeTimer = null;
    }
};


// ─────────────────────────────────────────────────────────
// Logs
// ─────────────────────────────────────────────────────────
function addLog(msg) {
  const box = document.getElementById("logBox");
  if (!box) return;

  const time = new Date().toTimeString().slice(0, 8);
  box.innerHTML +=
    `<div><span style="color:var(--primary);font-weight:600">${time}</span> ${msg}</div>`;

  box.scrollTop = box.scrollHeight;
}


// ─────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────
function showToast(msg, ms = 3500) {
  const t = document.getElementById("toast");
  if (!t) return;

  document.getElementById("toastMessage").textContent = msg;
  t.style.display = "block";

  requestAnimationFrame(() => t.classList.add("show"));

  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => (t.style.display = "none"), 300);
  }, ms);
}


// ─────────────────────────────────────────────────────────
// TRAINING (ONLY PYTHON CONTROLS CAMERA)
// ─────────────────────────────────────────────────────────
function startTraining() {

    if (!bridge) {
        alert("Bridge not connected!");
        return;
    }

    showToast("Training started. Capturing images...", 4000);
    addLog("Training started...");

    startUptime();

    try {
        bridge.startTraining();
    }
    catch (err) {
        console.error(err);
        showToast("Training start failed", 3000);
    }
}

function stopTraining() {

    if (!bridge) return;

    try {
        bridge.stopTraining();
    } catch (e) {
        console.log(e);
    }

    stopUptime();
    addLog("Training stopped.");
}


// ─────────────────────────────────────────────────────────
// Settings UI (kept from your code)
// ─────────────────────────────────────────────────────────
function openSettings() {
  document.getElementById("settingsModal").style.display = "flex";
}

function closeSettings() {
  document.getElementById("settingsModal").style.display = "none";
}

function saveSettings() {
  closeSettings();
  showToast("Settings saved successfully");
  addLog("Settings updated.");
}


// ─────────────────────────────────────────────────────────
// Range Slider Fill
// ─────────────────────────────────────────────────────────
document.querySelectorAll('input[type="range"]').forEach((slider) => {
  updateRangeFill(slider);
  slider.addEventListener("input", () => updateRangeFill(slider));
});

function updateRangeFill(slider) {
  const percentage =
    ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
  slider.style.setProperty("--value", percentage + "%");
}

setTimeout(()=>{
    console.log("Bridge Object =", bridge);
},2000);

// What Is Removed

// ❌ navigator.mediaDevices

// ❌ getUserMedia

// ❌ fetch("/start")

// ❌ fetch("/stop")

// ❌ Demo defect interval

// ❌ Duplicate startTraining

// ❌ _activate / _deactivate

// ❌ Browser camera switching