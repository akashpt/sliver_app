// ─── Helpers ──────────────────────────────────────────────────────────
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setStyle(id, prop, value) {
  const el = document.getElementById(id);
  if (el) el.style.setProperty(prop, value);
}

// ─── Clock & Uptime ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Clock
  const updateClock = () => setText('clock', new Date().toTimeString().slice(0, 8));
  updateClock();
  setInterval(updateClock, 1000);

  // Uptime
  let sessionStart = null;
  let uptimeTimer = null;

  window.startUptime = () => {
    sessionStart = Date.now();
    uptimeTimer = setInterval(() => {
      const uptimeEl = document.getElementById('uptimeVal');
      if (uptimeEl) {
        const s = Math.floor((Date.now() - sessionStart) / 1000);
        uptimeEl.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
      }
    }, 1000);
  };

  window.stopUptime = () => {
    if (uptimeTimer) {
      clearInterval(uptimeTimer);
      uptimeTimer = null;
    }
  };
});

// ─── Logs ─────────────────────────────────────────────────────────────
function addLog(msg) {
  const box = document.getElementById('logBox');
  if (!box) return;
  const time = new Date().toTimeString().slice(0, 8);
  box.innerHTML += `<div><span style="color:var(--primary);font-weight:600">${time}</span> ${msg}</div>`;
  box.scrollTop = box.scrollHeight;
}

// ─── Defect Slider UI Helpers ──────────────────────────────────────────
let defectHistory = [];
let currentModalIndex = -1;

function addDefectImage(imgSrc) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  defectHistory.unshift({ time, src: imgSrc });
  if (defectHistory.length > 10) defectHistory.pop();
  renderDefectThumbs();
}

function renderDefectThumbs() {
  const container = document.getElementById('defectsSlider');
  if (!container) return;
  container.innerHTML = '';

  if (defectHistory.length === 0) {
    container.innerHTML = '<div class="defect-empty">No defects detected yet in this session</div>';
    return;
  }

  defectHistory.forEach((def, idx) => {
    const thumb = document.createElement('div');
    thumb.className = 'defect-thumb';
    thumb.innerHTML = `<img src="${def.src}" alt="Defect ${idx + 1}" loading="lazy">`;
    thumb.onclick = () => openDefectModal(idx);
    container.appendChild(thumb);
  });
}

function openDefectModal(index) {
  currentModalIndex = index;
  updateModalImage();
  setStyle('defectModal', 'display', 'flex');
}

function updateModalImage() {
  if (currentModalIndex < 0 || currentModalIndex >= defectHistory.length) {
    closeDefectModal();
    return;
  }
  const def = defectHistory[currentModalIndex];
  const imgEl = document.getElementById('defectModalImage');
  const posEl = document.getElementById('defectModalPosition');
  if (imgEl) imgEl.src = def.src;
  if (posEl) posEl.textContent = `${currentModalIndex + 1} / ${defectHistory.length} — ${def.time}`;

  setText('prevDefect', currentModalIndex === 0 ? 'disabled' : '');
  setText('nextDefect', currentModalIndex === defectHistory.length - 1 ? 'disabled' : '');
}

function changeDefect(direction) {
  currentModalIndex += direction;
  updateModalImage();
}

function closeDefectModal() {
  setStyle('defectModal', 'display', 'none');
  currentModalIndex = -1;
}

function downloadDefectImage() {
  if (currentModalIndex < 0 || currentModalIndex >= defectHistory.length) return;
  const img = document.getElementById('defectModalImage');
  const a = document.createElement('a');
  a.href = img.src;
  a.download = `defect_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.jpg`;
  a.click();
}

// ─── Toast ───────────────────────────────────────────────────────
function showToast(msg, ms = 3500) {
  const t = document.getElementById('toast');
  if (!t) return;
  setText('toastMessage', msg);
  setStyle('toast', 'display', 'block');
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => setStyle('toast', 'display', 'none'), 300);
  }, ms);
}

// ─── UI Helpers for Live Feed & Stats ───────────────────────────
function updateFrame(b64img) {
  const video = document.getElementById('videoFeed');
  if (video) video.src = b64img;
}

function updateStats(inspected, good, bad) {
  setText('inspectedCount', inspected);
  setText('goodCount', good);
  setText('badCount', bad);
  setText('hdrDefects', bad);
}

// ─── Qt WebChannel Bridge Setup ──────────────────────────────────────
let bridge = null;

document.addEventListener('DOMContentLoaded', () => {

  if (typeof QWebChannel === 'undefined') {
    console.error('QWebChannel not loaded! Make sure qwebchannel.js is included in <head>.');
    return;
  }

  new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
    console.log('WebChannel connected:', bridge);
  

    // Connect Python signals to JS
    if (bridge.frameUpdate) {
      bridge.frameUpdate.connect(function(b64img) {
        updateFrame(b64img);
      });
    }

    if (bridge.statsUpdate) {
      bridge.statsUpdate.connect(function(inspected, good, bad) {
        updateStats(inspected, good, bad);
      });
    }

    if (bridge.defectFound) {
      bridge.defectFound.connect(function(path) {
        showToast('DEFECT DETECTED!', 5000);
        addDefectImage(path);
        stopDetection();
 // stop UI detection visuals
      });
    }
  });
});

// ─── Start / Stop Detection Buttons ─────────────────────────────────
function startDetection() {
  if (bridge && typeof bridge.startDetection === "function") {
    bridge.startDetection();
  } else {
    console.error("bridge.startDetection not available yet");
  }
}

function stopDetection() {
  if (bridge && typeof bridge.stopDetection === "function") {
    bridge.stopDetection();
  } else {
    console.error("bridge.stopDetection not available yet");
  }
}
function updateFrame(b64img) {
  const img = document.getElementById("videoFeed");
  const noFeed = document.getElementById("noFeed");

  if (img && b64img) {
    img.style.display = "block";
    img.src = "";
    img.src = b64img;
  }

  if (noFeed) {
    noFeed.style.display = "none";
  }
}
// function updateFrame(b64img) {
//   const img = document.getElementById('videoFeed');
//   if (img) {
//     // img.style.display = "block";       // show image
//     img.src = b64img;                  // base64 data URI
//   }
// }
function updateModalImage() {
  if (currentModalIndex < 0 || currentModalIndex >= defectHistory.length) {
    closeDefectModal();
    return;
  }

  const def = defectHistory[currentModalIndex];

  const imgEl = document.getElementById('defectModalImage');
  const posEl = document.getElementById('defectModalPosition');

  if (imgEl) imgEl.src = def.src;

  if (posEl)
    posEl.textContent =
      `${currentModalIndex + 1} / ${defectHistory.length} — ${def.time}`;

  // ⭐ Fix arrow button enabling/disabling
  document.getElementById("prevDefect").disabled =
    currentModalIndex === 0;

  document.getElementById("nextDefect").disabled =
    currentModalIndex === defectHistory.length - 1;
}

