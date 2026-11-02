// Base URL handles both local testing and decoupled cloud deployment
const API_BASE = "";

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
const systemStatus = document.querySelector('.system-status');

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

// PDF Guide Modal Handles
const btnGuideExport = document.getElementById('btnGuideExport');
const guideModal = document.getElementById('guideModal');
const guideLanguage = document.getElementById('guideLanguage');
const btnCreateGuide = document.getElementById('btnCreateGuide');
const btnCancelGuide = document.getElementById('btnCancelGuide');

// On-Screen Language Toggle Handles
const btnLangEn = document.getElementById('btnLangEn');
const btnLangBn = document.getElementById('btnLangBn');
const langLoader = document.getElementById('langLoader');

// Section Heading Handles for On-Screen Translation
const labelPathogen = document.getElementById('labelPathogen');
const labelConfidence = document.getElementById('labelConfidence');
const labelSeverity = document.getElementById('labelSeverity');
const labelSymptoms = document.getElementById('labelSymptoms');
const labelCauses = document.getElementById('labelCauses');
const labelTreatments = document.getElementById('labelTreatments');
const labelOrganic = document.getElementById('labelOrganic');
const labelPreventions = document.getElementById('labelPreventions');

// Diagnostic Caches & Active Language State
let latestDiagnosis = null;
let englishDiagnosis = null;
let bengaliDiagnosis = null;
let currentLanguage = "English";

// Localized UI Labels
const UI_LABELS = {
  English: {
    pathogen: "Pathogen Class",
    confidence: "Confidence",
    severity: "Severity",
    symptoms: "Observed Symptoms",
    causes: "Etiology & Causes",
    treatments: "Immediate Chemical / Field Treatments",
    organic: "Eco-Friendly & Organic Remedies",
    preventions: "Long-Term Prevention Plan",
    exportBtn: "Print / Save Clinical Notes",
    healthy: "Healthy",
    infected: "Infected"
  },
  Bengali: {
    pathogen: "রোগ সৃষ্টিকারী জীবাণু",
    confidence: "নির্ভুলতার হার",
    severity: "তীব্রতার মাত্রা",
    symptoms: "লক্ষণসমূহ",
    causes: "মূল কারণ",
    treatments: "জরুরী রাসায়নিক / মাঠের চিকিৎসা",
    organic: "পরিবেশবান্ধব ও জৈব প্রতিকার",
    preventions: "দীর্ঘমেয়াদী প্রতিরোধ ব্যবস্থা",
    exportBtn: "চিকিৎসা প্রেসক্রিপশন প্রিন্ট করুন",
    healthy: "সুস্থ ও স্বাভাবিক",
    infected: "সংক্রমিত / রোগাক্রান্ত"
  }
};

// ---------------------------------------------------------
// 1. Silent Warm-up Ping (Wakes Render Backend on Page Load)
// ---------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  fetch(`${API_BASE}/api/health`)
    .then(res => res.json())
    .then(() => {
      if (systemStatus) {
        systemStatus.innerHTML = '<span class="status-dot"></span> Engine Online';
        systemStatus.style.background = '#ecfdf5';
        systemStatus.style.borderColor = '#a7f3d0';
        systemStatus.style.color = '#059669';
      }
    })
    .catch(() => {
      if (systemStatus) {
        systemStatus.innerHTML = '<span class="status-dot" style="background:#f59e0b"></span> Waking Engine...';
      }
    });
});

// ---------------------------------------------------------
// 2. Sample Generators for Immediate Testing
// ---------------------------------------------------------
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

// ---------------------------------------------------------
// 3. Dropzone & File Handling
// ---------------------------------------------------------
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

// ---------------------------------------------------------
// 4. Sample Testing Buttons
// ---------------------------------------------------------
document.querySelectorAll('.sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.type;
    const canvas = document.createElement('canvas');
    canvas.width = 300;
    canvas.height = 300;
    if (sampleDrawers[type]) {
      sampleDrawers[type](canvas.getContext('2d'));
      canvas.toBlob(blob => {
        const file = new File([blob], `${type}_specimen.png`, { type: 'image/png' });
        loadImage(file);
      });
    }
  });
});

// ---------------------------------------------------------
// 5. Camera Video Capture
// ---------------------------------------------------------
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

// ---------------------------------------------------------
// 6. Diagnose Request
// ---------------------------------------------------------
btnDiagnose.addEventListener('click', async () => {
  if (!currentFile) return;

  scanLaser.classList.remove('hidden');
  btnDiagnose.disabled = true;
  btnDiagnose.textContent = "Analyzing Leaf Pathology...";

  const fd = new FormData();
  fd.append('leafImage', currentFile);

  try {
    const res = await fetch(`${API_BASE}/api/diagnose`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error("Diagnosis server response failed.");

    const data = await res.json();
    
    // Cache diagnosis & reset language toggle
    latestDiagnosis = data;
    englishDiagnosis = data;
    bengaliDiagnosis = null;
    currentLanguage = "English";

    if (btnLangEn && btnLangBn) {
      btnLangEn.classList.add('active');
      btnLangBn.classList.remove('active');
    }

    renderDiagnosis(data);
  } catch (err) {
    alert(err.message);
  } finally {
    scanLaser.classList.add('hidden');
    btnDiagnose.disabled = false;
    btnDiagnose.innerHTML = '<span class="btn-icon">🪄</span> Diagnose Leaf';
  }
});

// ---------------------------------------------------------
// 7. On-Screen Language Toggle Handlers
// ---------------------------------------------------------
if (btnLangEn) {
  btnLangEn.addEventListener('click', () => {
    if (currentLanguage === "English") return;
    currentLanguage = "English";
    btnLangEn.classList.add('active');
    if (btnLangBn) btnLangBn.classList.remove('active');
    if (englishDiagnosis) renderDiagnosis(englishDiagnosis);
  });
}

if (btnLangBn) {
  btnLangBn.addEventListener('click', async () => {
    if (currentLanguage === "Bengali") return;
    if (!englishDiagnosis) return;

    currentLanguage = "Bengali";
    btnLangBn.classList.add('active');
    if (btnLangEn) btnLangEn.classList.remove('active');

    // Return instant cached translation without extra API calls
    if (bengaliDiagnosis) {
      renderDiagnosis(bengaliDiagnosis);
      return;
    }

    // Call backend translation endpoint
    try {
      if (langLoader) langLoader.classList.remove('hidden');
      const res = await fetch(`${API_BASE}/api/treatment-guide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diagnosis: englishDiagnosis,
          language: "Bengali"
        })
      });

      if (!res.ok) throw new Error("Translation request failed.");
      const data = await res.json();
      bengaliDiagnosis = data.diagnosis;
      renderDiagnosis(bengaliDiagnosis);
    } catch (err) {
      alert("বাংলা অনুবাদ লোড করতে সমস্যা হয়েছে: " + err.message);
      if (btnLangEn) btnLangEn.click();
    } finally {
      if (langLoader) langLoader.classList.add('hidden');
    }
  });
}

// ---------------------------------------------------------
// 8. Render Diagnosis to DOM
// ---------------------------------------------------------
function renderDiagnosis(data) {
  emptyState.classList.add('hidden');
  diagnosticContent.classList.remove('hidden');

  // Update Section Titles
  const labels = UI_LABELS[currentLanguage] || UI_LABELS.English;
  if (labelPathogen) labelPathogen.textContent = labels.pathogen;
  if (labelConfidence) labelConfidence.textContent = labels.confidence;
  if (labelSeverity) labelSeverity.textContent = labels.severity;
  if (labelSymptoms) labelSymptoms.textContent = labels.symptoms;
  if (labelCauses) labelCauses.textContent = labels.causes;
  if (labelTreatments) labelTreatments.textContent = labels.treatments;
  if (labelOrganic) labelOrganic.textContent = labels.organic;
  if (labelPreventions) labelPreventions.textContent = labels.preventions;
  if (btnExport) btnExport.textContent = labels.exportBtn;

  // Populate Field Values
  resPlant.textContent = data.plantName || "Unknown Host";
  resCondition.textContent = data.conditionName || "Pathological Specimen";
  resPathogen.textContent = data.pathogenType || "None";
  resConfidence.textContent = `${data.confidenceScore}%`;
  resSeverity.textContent = data.severityRating || "None";

  const isHealthy = (data.healthStatus || "").toLowerCase().includes("healthy") || 
                    (data.healthStatus || "").includes("সুস্থ");
  resStatusPill.textContent = isHealthy ? labels.healthy : labels.infected;
  resStatusPill.className = `status-pill ${isHealthy ? 'healthy' : 'infected'}`;

  fillList(resSymptoms, data.symptoms);
  fillList(resCauses, data.causes);
  fillList(resTreatments, data.treatments);
  fillList(resOrganic, data.organicRemedies);
  fillList(resPreventions, data.preventions);
}

function fillList(el, items) {
  if (!el) return;
  el.innerHTML = '';
  if (!items || items.length === 0) {
    el.innerHTML = currentLanguage === "Bengali" 
      ? '<li>কোন তথ্যের প্রয়োজন নেই।</li>' 
      : '<li>None required or detected.</li>';
    return;
  }
  items.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    el.appendChild(li);
  });
}

// Print Current Screen View
btnExport.addEventListener('click', () => {
  window.print();
});

// ---------------------------------------------------------
// 9. Guide Modal Triggers & PDF Document Generation
// ---------------------------------------------------------
if (btnGuideExport && guideModal) {
  btnGuideExport.addEventListener('click', () => {
    if (!latestDiagnosis) return;
    guideModal.classList.remove('hidden');
  });
}

if (btnCancelGuide && guideModal) {
  btnCancelGuide.addEventListener('click', () => {
    guideModal.classList.add('hidden');
  });
}

if (btnCreateGuide) {
  btnCreateGuide.addEventListener('click', async () => {
    if (!latestDiagnosis) return;

    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      alert('Please allow pop-ups to create the PDF guide.');
      return;
    }

    btnCreateGuide.disabled = true;
    btnCreateGuide.textContent = 'Preparing guide...';
    try {
      const response = await fetch(`${API_BASE}/api/treatment-guide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ diagnosis: latestDiagnosis, language: guideLanguage.value })
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Treatment guide could not be created.');
      }
      const result = await response.json();
      printWindow.document.write(buildGuideDocument(result.diagnosis, result.language));
      printWindow.document.close();
      if (guideModal) guideModal.classList.add('hidden');
    } catch (err) {
      printWindow.close();
      alert(err.message);
    } finally {
      btnCreateGuide.disabled = false;
      btnCreateGuide.textContent = 'Create PDF Guide';
    }
  });
}

function buildGuideDocument(diagnosis, language) {
  const list = (items) => (items || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
  return `<!doctype html>
    <html lang="en"><head><meta charset="utf-8"><title>HarvestIQ Treatment Guide</title>
    <style>
      body{font-family:Arial,sans-serif;color:#172033;max-width:760px;margin:0 auto;padding:36px;line-height:1.5}
      h1{color:#166534;margin-bottom:4px} h2{color:#14532d;border-bottom:1px solid #bbf7d0;padding-bottom:6px}
      .meta{color:#475569;margin-bottom:24px}.notice{background:#f0fdf4;border:1px solid #bbf7d0;padding:12px;border-radius:6px}
      li{margin:7px 0} footer{border-top:1px solid #cbd5e1;margin-top:30px;padding-top:12px;color:#64748b;font-size:12px}
      @media print{body{padding:0}.no-print{display:none}}
    </style></head><body>
    <h1>HarvestIQ Treatment Guide</h1>
    <div class="meta"><strong>${escapeHtml(diagnosis.plantName || 'Unknown plant')}</strong> · ${escapeHtml(diagnosis.conditionName || 'Unknown condition')}<br>
    Guide language: ${escapeHtml(language)} · Confidence: ${escapeHtml(String(diagnosis.confidenceScore || 'N/A'))}%</div>
    <div class="notice"><strong>Important:</strong> This AI-generated guide is for educational support. Confirm the diagnosis and follow local pesticide labels or advice from a qualified agricultural professional before treatment.</div>
    <h2>Observed Symptoms</h2><ul>${list(diagnosis.symptoms)}</ul>
    <h2>Likely Causes</h2><ul>${list(diagnosis.causes)}</ul>
    <h2>Immediate Treatment</h2><ul>${list(diagnosis.treatments)}</ul>
    <h2>Organic Remedies</h2><ul>${list(diagnosis.organicRemedies)}</ul>
    <h2>Prevention</h2><ul>${list(diagnosis.preventions)}</ul>
    <footer>Generated by HarvestIQ AI Plant Pathology · Use your browser's print dialog and choose “Save as PDF”.</footer>
    <script>window.onload=()=>window.print();<\/script></body></html>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}
