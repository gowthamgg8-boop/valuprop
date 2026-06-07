/**
 * ValUprop.in — Detail Report Page JS
 * js/detail.js
 */

const BACKEND_URL = window.BACKEND_URL || 'https://valuprop-api.onrender.com';
const MAX_POLLS   = 90;   // 90 × 3 s = 270 s (4.5 min) max wait
let   pollCount   = 0;

document.addEventListener('DOMContentLoaded', function () {
  if (!isPaid()) { window.location.href = 'results.html'; return; }
  const paidValId = sessionStorage.getItem('valuprop_paid_val_id');
  if (!paidValId) { renderDemoReport(); return; }
  pollForReport(parseInt(paidValId));
});

async function pollForReport(valuation_id) {
  try {
    const token = sessionStorage.getItem('valuprop_paid_access_token') || '';
    const url = `${BACKEND_URL}/api/valuation/paid/${valuation_id}` + (token ? `?token=${encodeURIComponent(token)}` : '');
    const resp = await fetch(url);
    const data = await resp.json();
    if (resp.status === 401 || resp.status === 403) { showError('Access denied. Please email info@myriky.com with ref: VUP-' + valuation_id); return; }
    if (data.status === 'pending') {
      pollCount++;
      if (pollCount >= MAX_POLLS) { showError('Report taking longer than expected. Please email info@myriky.com with ref: VUP-' + valuation_id); return; }
      setTimeout(() => pollForReport(valuation_id), 3000); return;
    }
    if (data.status === 'error') { showError(data.message || 'Report failed. Contact info@myriky.com'); return; }
    if (data.status === 'ready') { renderReport(data.report, data.value_min, data.value_max, data.confidence, valuation_id); }
  } catch (e) { console.warn('Poll failed:', e); renderDemoReport(); }
}

function renderReport(report, valueMin, valueMax, confidence, valId) {
  document.getElementById('report-loading').style.display = 'none';
  document.getElementById('report-content').style.display = 'block';
  const search = getSearch();
  document.getElementById('r-ref').textContent        = `VUP-${String(valId).padStart(5,'0')}`;
  document.getElementById('r-ref-bottom').textContent = `VUP-${String(valId).padStart(5,'0')}`;
  document.getElementById('r-address').textContent    = search.address || search.locality || 'Property';
  document.getElementById('r-email').textContent      = search.email || 'your email address';
  document.getElementById('r-value').textContent = `${fmtL(valueMin)} – ${fmtL(valueMax)}`;
  const conf = confidence || 70;
  document.getElementById('r-confidence-text').textContent = `Confidence: ${conf}% — ${confLabel(conf)}`;
  document.getElementById('r-confidence-pill').className   = 'confidence-pill ' + confClass(conf);
  if (conf < 70) document.getElementById('r-confidence-warn').style.display = 'block';

  const secs = report.sections || report;

  // Section A
  setText('sec-a', secs.A?.content || secs.asset_overview || '');

  // Section B
  setText('sec-b', secs.B?.content || secs.micro_market || '');

  // Section C
  const cSec = secs.C || {};
  buildTable('sec-c-table', [
    ['Land Rate Range', cSec.land_rate_range || ''],
    ['Apartment Rate',  cSec.apt_rate_range  || ''],
    ['12-Month Trend',  cSec.trend           || ''],
    ['Guideline Value', cSec.guideline_value || ''],
  ]);
  setText('sec-c-content', cSec.content || secs.pricing_signals || '');

  // Section D — parse structured pipe format
  const dSec = secs.D || {};
  const rawD = dSec.content || secs.valuation_buildup || '';
  renderSectionD(rawD, dSec);

  // Section E
  const eSec = secs.E || {};
  document.getElementById('sec-e-range').textContent = eSec.value_range || `${fmtL(valueMin)} – ${fmtL(valueMax)}`;
  setText('sec-e-content', eSec.content || secs.value_opinion || '');

  // Section F
  const fSec  = secs.F || {};
  const risks = fSec.risk_points || parseBullets(secs.risk_diligence || '');
  document.getElementById('sec-f-list').innerHTML = risks
    .filter(r => r.trim())
    .map(r => `<li><div class="risk-dot"></div><span>${r.replace(/^[•\-\*]\s*/,'')}</span></li>`)
    .join('');

  // Comparables
  const comps = report.comparables || [];
  if (comps.length > 0) {
    document.getElementById('comp-card').style.display = 'block';
    document.getElementById('comp-list').innerHTML = comps.map(c => `
      <div class="comp-item">
        <div><div class="comp-desc">${c.description||''}</div><div class="comp-source">${c.source||''}</div></div>
        <div class="comp-price">${c.price_signal||''}</div>
      </div>`).join('');
  }

  // Section G
  const gSec = secs.G || {};
  document.getElementById('sec-g').textContent = gSec.content || secs.disclaimer || 'This AI-generated valuation is for informational purposes only.';
}

function renderSectionD(raw, dSec) {
  // If no pipe-format, fall back to simple table + text
  if (!raw || (!raw.includes('STEPS|') && !raw.includes('ADJ|'))) {
    buildTable('sec-d-table', [
      ['Land Value',             dSec.land_value     || ''],
      ['Building Value (Depr.)', dSec.building_value || ''],
      ['Location Adjustments',   dSec.adjustments    || ''],
    ]);
    setText('sec-d-content', raw || '');
    return;
  }

  // Parse structured pipe format
  const lines = raw.split('\n').filter(l => l.trim());
  let stepRows=[], adjRows=[], yieldRows=[], noteText='', finalVal='';

  lines.forEach(line => {
    const p = line.split('|');
    const tag = p[0];
    if (tag==='STEPS' && p.length>=5) stepRows.push(p.slice(1,5));
    else if (tag==='ADJ' && p.length>=3) adjRows.push(p.slice(1,4));
    else if (tag==='FINAL') finalVal = p[4]||'';
    else if (tag==='YIELD' && p.length>=6) yieldRows.push(p.slice(1,6));
    else if (tag==='NOTE') noteText = p.slice(1).join('|');
  });

  const ts = 'width:100%;border-collapse:collapse;font-size:13px;margin-bottom:10px;';
  const th = 'padding:6px 8px;background:#f6f7fa;color:#6b7280;font-size:11px;font-weight:700;border-bottom:1.5px solid #e0e4ec;text-align:left;';
  const td = 'padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:13px;';

  let html = '';

  if (stepRows.length) {
    html += `<table style="${ts}"><thead><tr>
      <th style="${th}">STEP</th><th style="${th}">COMPONENT</th>
      <th style="${th}">CALCULATION</th><th style="${th}">VALUE</th>
    </tr></thead><tbody>`;
    stepRows.forEach(r => html += `<tr><td style="${td}"><b>${r[0]}</b></td><td style="${td}">${r[1]}</td><td style="${td}">${r[2]}</td><td style="${td}"><b>${r[3]}</b></td></tr>`);
    if (finalVal) html += `<tr style="background:#EBF3FF"><td style="${td}"></td><td style="${td}"><b>FINAL VALUE</b></td><td style="${td}"></td><td style="${td};color:#1B3F6E;font-weight:700">${finalVal}</td></tr>`;
    html += '</tbody></table>';
  }

  if (adjRows.length) {
    html += `<table style="${ts}"><thead><tr>
      <th style="${th}">STEP 5 ADJUSTMENTS</th><th style="${th}">FACTOR</th><th style="${th}">APPLIED</th>
    </tr></thead><tbody>`;
    adjRows.forEach(r => {
      const isNet = r[0].includes('NET');
      const bg = isNet ? 'background:#f0f4ff;' : '';
      html += `<tr style="${bg}"><td style="${td}">${isNet?'<b>':''}{r[0]}${isNet?'</b>':''}</td>`.replace('{r[0]}',r[0]) +
              `<td style="${td};font-weight:600">${r[1]}</td><td style="${td}">${r[2]||''}</td></tr>`;
    });
    html += '</tbody></table>';
  }

  if (yieldRows.length) {
    html += `<table style="${ts}"><thead><tr>
      <th style="${th}">SCENARIO</th><th style="${th}">MONTHLY RENT</th>
      <th style="${th}">ANNUAL RENT</th><th style="${th}">CAPITAL VALUE</th>
      <th style="${th}">GROSS YIELD</th>
    </tr></thead><tbody>`;
    yieldRows.forEach(r => html += `<tr>
      <td style="${td}"><b>${r[0]}</b></td><td style="${td}">${r[1]}</td>
      <td style="${td}">${r[2]}</td><td style="${td}">${r[3]}</td>
      <td style="${td};color:#1A7A4A;font-weight:700">${r[4]}</td></tr>`);
    html += '</tbody></table>';
    if (noteText) html += `<p style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:6px;padding:8px 12px;font-size:12px;color:#065f46;margin-top:4px;">${noteText}</p>`;
  }

  const el = document.getElementById('sec-d-content');
  if (el) { el.innerHTML = html; }
  const tbl = document.getElementById('sec-d-table');
  if (tbl) tbl.style.display = 'none';
}

// Demo mode
function renderDemoReport() {
  const search = getSearch();
  const demoData = getDemoData(search);
  renderReport(demoData.report, demoData.value_min, demoData.value_max, demoData.confidence, 0);
}

function getDemoData(search) {
  const loc = search.locality || 'Anna Nagar';
  const city = search.city || 'Chennai';
  const type = search.type || 'Apartment';
  const bhk  = search.bhk || '2BHK';
  const ranges = { Apartment:[48,74], IndependentHouse:[280,420], Villa:[380,560], LandPlot:[60,95] };
  const [lo, hi] = ranges[type] || [48,74];
  return {
    value_min: lo, value_max: hi, confidence: 78,
    report: {
      sections: {
        A: { content: `This ${type.replace('IndependentHouse','Independent House')} is located in ${loc}, ${city}. ${search.carpetArea?'Carpet area: '+search.carpetArea+' sq.ft. ':''} ${search.bhk?bhk+'. ':''} Well-established locality with good connectivity.` },
        B: { content: `${loc} is a mature residential micro-market in ${city}, characterised by strong end-user demand and steady appreciation.` },
        C: { land_rate_range: city==='Bangalore'?'Rs.12,000-Rs.22,000/sq.ft':'Rs.10,000-Rs.18,000/sq.ft', apt_rate_range: city==='Bangalore'?'Rs.7,000-Rs.11,000/sq.ft':'Rs.6,500-Rs.10,000/sq.ft', guideline_value: city==='Bangalore'?'Rs.5,500-Rs.8,000/sq.ft':'Rs.4,500-Rs.7,500/sq.ft', content: `Land rates in ${loc} are supported by strong demand. Government guideline values remain below market.` },
        D: { land_value: `${fmtL(Math.round(lo*0.72))} – ${fmtL(Math.round(hi*0.72))}`, building_value: `${fmtL(Math.round(lo*0.20))} – ${fmtL(Math.round(hi*0.20))}`, adjustments: `+${fmtL(Math.round(lo*0.08))} – +${fmtL(Math.round(hi*0.08))}`, content: `Valuation components: land + building + location adjustments.` },
        E: { value_range: `${fmtL(Math.round(lo*1.02))} – ${fmtL(Math.round(hi*0.98))}`, content: `Estimated market value based on locality benchmarks and comparable signals.` },
        F: { risk_points: ['Verify title deed and encumbrance certificate before transacting.','Confirm building approval (CMDA/DTCP) and Occupancy Certificate.','Inspect physical condition — standard construction assumed.','Verify property tax and no outstanding dues.','For apartments: confirm society NOC and maintenance dues.'] },
        G: { content: 'This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation.' },
      },
      comparables: [
        { description: `Similar 2BHK in ${loc}`, price_signal: `${fmtL(Math.round(lo*0.95))} – ${fmtL(Math.round(lo*1.05))}`, source: 'Locality database' },
        { description: `Comparable in ${loc} adjacent`, price_signal: `${fmtL(Math.round(hi*0.92))} – ${fmtL(Math.round(hi*1.00))}`, source: 'Locality database' },
      ],
    },
  };
}

// Helpers
function fmtL(l) { if(!l&&l!==0) return '—'; if(l>=100) return `₹${(l/100).toFixed(2)} Cr`; return `₹${l} L`; }
function confLabel(c) { if(c>=80) return 'Good'; if(c>=65) return 'Moderate'; return 'Low'; }
function confClass(c) { if(c>=70) return 'confidence-high'; if(c>=50) return 'confidence-medium'; return 'confidence-low'; }
function setText(id, text) { const el=document.getElementById(id); if(el) el.textContent=text||''; }
function buildTable(id, rows) { const el=document.getElementById(id); if(!el) return; el.innerHTML=rows.filter(([,v])=>v).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join(''); }
function parseBullets(text) { if(!text) return []; return text.split('\n').map(l=>l.replace(/^[•\-\*]\s*/,'').trim()).filter(Boolean); }
function showError(msg) { document.getElementById('report-loading').innerHTML=`<div style="max-width:420px;margin:0 auto;text-align:center;padding:60px 20px;"><div style="font-size:40px;margin-bottom:16px;">⚠️</div><h2 style="font-family:var(--font-head);font-size:18px;margin-bottom:10px;">Report issue</h2><p style="font-size:14px;color:var(--muted);">${msg}</p></div>`; }
function shareReport() { const search=getSearch(); const text=`My ValUprop estimate for ${search.locality||'my property'}: ${document.getElementById('r-value')?.textContent||''}. Get yours at valuprop.in`; if(navigator.share){navigator.share({title:'ValUprop',text}).catch(()=>{});}else{navigator.clipboard.writeText(text).then(()=>alert('Copied!'));} }
function downloadPdf() {
  const paidValId=sessionStorage.getItem('valuprop_paid_val_id');
  const btn=document.getElementById('btn-download');
  if(!paidValId){window.print();return;}
  if(btn){btn.textContent='⏳ Preparing…';btn.disabled=true;}
  const token=sessionStorage.getItem('valuprop_paid_access_token')||'';
  const url=`${BACKEND_URL}/api/report/${paidValId}/pdf`+(token?`?token=${encodeURIComponent(token)}`:'');
  const a=document.createElement('a'); a.href=url; a.download=`ValUprop-Report-VUP-${String(paidValId).padStart(5,'0')}.pdf`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(()=>{if(btn){btn.textContent='⬇ Download PDF';btn.disabled=false;}},3000);
}
