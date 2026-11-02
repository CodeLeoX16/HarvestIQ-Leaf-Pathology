let currentFile = null;
let cameraStream = null;

// UI DOM Handles
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const dropzonePrompt = document.getElementById('dropzonePrompt');
const previewArea = document.getElementById('previewArea');
const leafPreview = document.getElementById('leafPreview');
const scanLaser = document.getElementById('scanLaser');
const btnClearImage = document.getElementById('btnClearImage');
const btnDiagnose = document.getElementById('btnDiagnose');
const btnCamera = document.getElementById('btnCamera');

// Camera Modal Handles
const cameraModal = document.getElementById('cameraModal');
const cameraVideo = document.getElementById('cameraVideo');
const btnTakeSnap = document.getElementById('btnTakeSnap');
const btnCancelCamera = document.getElementById('btnCancelCamera');

// Result View Handles
const emptyState = document.getElementById('emptyState');
const diagnosticContent = document.getElementById('diagnosticContent');
const resPlant = document.getElementById('resPlant');
const resCondition = document.getElementById('resCondition');
const resStatusPill = document.getElementById('resStatusPill');
const resPathogen = document.getElementById('resPathogen');
const resConfidence = document.getElementById('resConfidence');
const resSeverity = document.getElementById('resSeverity');
const resSymptoms = document.getElementById('resSymptoms');
const resCauses = document.getElementById('resCauses');
const resTreatments = document.getElementById('resTreatments');
const resOrganic = document.getElementById('resOrganic');
const resPreventions = document.getElementById('resPreventions');
const btnExport = document.getElementById('btnExport');

// Sample Generators for Immediate Testing
const sampleDrawers = {
  apple: (ctx) => {
    ctx.fillStyle = "#166534"; ctx.fillRect(0, 0, 300, 300);
    ctx.fillStyle = "#1c1917"; 
    ctx.beginPath(); ctx.arc(120, 110, 32, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(190, 180, 24, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#ca8a04"; ctx.lineWidth = 4; ctx.stroke();
  },
  tomato: (ctx) => {
    ctx.fillStyle = "#3f6212"; ctx.fillRect(0, 0, 300, 300);
    ctx.fillStyle = "#451a03"; 
    ctx.beginPath(); ctx.arc(130, 140, 40, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#eab308"; ctx.lineWidth = 5; ctx.stroke();
  },
  corn: (ctx) => {
    ctx.fillStyle = "#65a30d"; ctx.fillRect(0, 0, 300, 300);
    ctx.fillStyle = "#c2410c";
    for (let i = 0; i < 10; i++) {
      ctx.beginPath(); 
      ctx.arc(50 + i * 22, 60 + (i % 3) * 60, 7, 0, Math.PI * 2); 
      ctx.fill();
    }
  },
  healthy: (ctx) => {
    ctx.fillStyle = "#15803d"; ctx.fillRect(0, 0, 300, 300);
    ctx.fillStyle = "#22c55e"; 
    ctx.beginPath(); ctx.arc(150, 150, 95, 0, Math.PI * 2); ctx.fill();
  }
};

// Dropzone file handling
dropzone.addEventListener('click', () => {
  if (!currentFile) fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files && e.target.files[0]) {
    loadImage(e.target.files[0]);
  }
});

dropzone.addEventListener('dragover', (e) => e.preventDefault());
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    loadImage(e.dataTransfer.files[0]);
  }
});

btnClearImage.addEventListener('click', (e) => {
  e.stopPropagation();
  currentFile = null;
  fileInput.value = '';
  previewArea.classList.add('hidden');
  dropzonePrompt.classList.remove('hidden');
  btnDiagnose.disabled = true;
  btnDiagnose.classList.remove('ready');
});

function loadImage(file) {
  currentFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    leafPreview.src = e.target.result;
    dropzonePrompt.classList.add('hidden');
    previewArea.classList.remove('hidden');
    btnDiagnose.disabled = false;
    btnDiagnose.classList.add('ready');
  };
  reader.readAsDataURL(file);
}

// Sample Card triggers
document.querySelectorAll('.sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.type;
    const canvas = document.createElement('canvas');
    canvas.width = 300;
    canvas.height = 300;
    sampleDrawers[type](canvas.getContext('2d'));
    canvas.toBlob(blob => {
      const file = new File([blob], `${type}_specimen.png`, { type: 'image/png' });
      loadImage(file);
    });
  });
});

// Camera stream triggers
btnCamera.addEventListener('click', async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    cameraVideo.srcObject = cameraStream;
    cameraModal.classList.remove('hidden');
  } catch (err) {
    alert("Camera permission denied or camera unavailable: " + err.message);
  }
});

btnCancelCamera.addEventListener('click', () => {
  if (cameraStream) cameraStream.getTracks().forEach(t => t.stop());
  cameraModal.classList.add('hidden');
});

btnTakeSnap.addEventListener('click', () => {
  const canvas = document.createElement('canvas');
  canvas.width = cameraVideo.videoWidth;
  canvas.height = cameraVideo.videoHeight;
  canvas.getContext('2d').drawImage(cameraVideo, 0, 0);
  canvas.toBlob(blob => {
    const file = new File([blob], 'camera_specimen.jpg', { type: 'image/jpeg' });
    loadImage(file);
    if (cameraStream) cameraStream.getTracks().forEach(t => t.stop());
    cameraModal.classList.add('hidden');
  }, 'image/jpeg');
});

// Run Diagnosis
btnDiagnose.addEventListener('click', async () => {
  if (!currentFile) return;

  scanLaser.classList.remove('hidden');
  btnDiagnose.disabled = true;
  btnDiagnose.textContent = "Analyzing Leaf Pathology...";

  const fd = new FormData();
  fd.append('leafImage', currentFile);

  try {
    const res = await fetch('/api/diagnose', { method: 'POST', body: fd });
    if (!res.ok) throw new Error("Diagnosis server response failed.");

    const data = await res.json();
    renderDiagnosis(data);
  } catch (err) {
    alert(err.message);
  } finally {
    scanLaser.classList.add('hidden');
    btnDiagnose.disabled = false;
    btnDiagnose.innerHTML = '<span class="btn-icon">🪄</span> Diagnose Leaf';
  }
});

function renderDiagnosis(data) {
  emptyState.classList.add('hidden');
  diagnosticContent.classList.remove('hidden');

  resPlant.textContent = data.plantName || "Unknown Host";
  resCondition.textContent = data.conditionName || "Pathological Specimen";
  resPathogen.textContent = data.pathogenType || "None";
  resConfidence.textContent = `${data.confidenceScore}%`;
  resSeverity.textContent = data.severityRating || "None";

  const isHealthy = (data.healthStatus || "").toLowerCase() === "healthy";
  resStatusPill.textContent = isHealthy ? "Healthy" : "Infected";
  resStatusPill.className = `status-pill ${isHealthy ? 'healthy' : 'infected'}`;

  fillList(resSymptoms, data.symptoms);
  fillList(resCauses, data.causes);
  fillList(resTreatments, data.treatments);
  fillList(resOrganic, data.organicRemedies);
  fillList(resPreventions, data.preventions);
}

function fillList(el, items) {
  el.innerHTML = '';
  if (!items || items.length === 0) {
    el.innerHTML = '<li>None required or detected.</li>';
    return;
  }
  items.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    el.appendChild(li);
  });
}

btnExport.addEventListener('click', () => {
  window.print();
});