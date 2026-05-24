/**
 * ValUprop.in — Detail Report Page JS
 * js/detail.js
 *
 * Polls backend for paid valuation result and renders
 * the full 7-section report into detail.html
 */

const BACKEND_URL = window.BACKEND_URL || 'https://valuprop-api.onrender.com';
const MAX_POLLS   = 30;    // 30 × 2s = 60s max wait
let   pollCount   = 0;

document.addEventListener('DOMContentLoaded', function () {
  if (!isPaid()) {
    window.location.href = 'results.html';
    return;
  }

  const paidValId = sessionStorage.getItem('valuprop_paid_val_id');

  if (!paidValId) {
    // No backend — render from session (demo mode)
    renderDemoReport();
    return;
  }

  // Poll backend for paid report
  pollForReport(parseInt(paidValId));
});


// ─── Backend polling ─────────────────────────────────────────────

async function pollForReport(valuation_id) {
  try {
    // OWASP A01 — paid endpoint requires the access_token issued at payment/verify.
    // Stored alongside valuprop_paid_val_id by payment.html on a successful pay.
    const token = sessionStorage.getItem('valuprop_paid_access_token') || '';
    const url = `${BACKEND_URL}/api/valuation/paid/${valuation_id}`
              + (token ? `?token=${encodeURIComponent(token)}` : '');
    const resp = await fetch(url);
    const data = await resp.json();

    if (resp.status === 401 || resp.status === 403) {
      showError('Access denied. Your session may have expired — please re-purchase the report or email info@myriky.com with ref: VUP-' + valuation_id);
      return;
    }

    if (data.status === 'pending') {
      pollCount++;
      if (pollCount >= MAX_POLLS) {
        showError('Report generation is taking longer than expected. Please email info@myriky.com with ref: VUP-' + valuation_id);
        return;
      }
      setTimeout(() => pollForReport(valuation_id), 2000);
      return;
    }

    if (data.status === 'error') {
      showError(data.message || 'Report generation failed. Please contact info@myriky.com');
      return;
    }

    if (data.status === 'ready') {
      renderReport(data.report, data.value_min, data.value_max, data.confidence, valuation_id);
    }
  } catch (e) {
    console.warn('Backend poll failed, using demo render:', e);
    renderDemoReport();
  }
}


// ─── Report renderer ─────────────────────────────────────────────

function renderReport(report, valueMin, valueMax, confidence, valId) {
  document.getElementById('report-loading').style.display = 'none';
  document.getElementById('report-content').style.display = 'block';

  const search = getSearch();

  // Ref + address
  document.getElementById('r-ref').textContent        = `VUP-${String(valId).padStart(5,'0')}`;
  document.getElementById('r-ref-bottom').textContent = `VUP-${String(valId).padStart(5,'0')}`;
  document.getElementById('r-address').textContent    = search.address || search.locality || 'Property';
  document.getElementById('r-email').textContent      = search.email || 'your email address';

  // Value range
  document.getElementById('r-value').textContent = `${fmtL(valueMin)} – ${fmtL(valueMax)}`;

  // Confidence
  const confPill = document.getElementById('r-confidence-pill');
  const confText = document.getElementById('r-confidence-text');
  const conf     = confidence || 70;
  confText.textContent = `Confidence: ${conf}% — ${confLabel(conf)}`;
  confPill.className   = 'confidence-pill ' + confClass(conf);
  if (conf < 70) {
    document.getElementById('r-confidence-warn').style.display = 'block';
  }

  // Sections
  const secs = report.sections || report;

  // Section A
  setText('sec-a', secs.A?.content || secs.asset_overview || '');

  // Section B
  setText('sec-b', secs.B?.content || secs.micro_market || '');

  // Section C — table + content
  const cSec = secs.C || {};
  buildTable('sec-c-table', [
    ['Land Rate Range',    cSec.land_rate_range  || ''],
    ['Apartment Rate',     cSec.apt_rate_range   || ''],
    ['Guideline Value',    cSec.guideline_value  || ''],
  ]);
  setText('sec-c-content', cSec.content || secs.pricing_signals || '');

  // Section D — table + content
  const dSec = secs.D || {};
  buildTable('sec-d-table', [
    ['Land Value',            dSec.land_value    || ''],
    ['Building Value (Depr.)',dSec.building_value|| ''],
    ['Location Adjustments',  dSec.adjustments   || ''],
  ]);
  setText('sec-d-content', dSec.content || secs.valuation_buildup || '');

  // Section E — tighter range + conclusion
  const eSec = secs.E || {};
  document.getElementById('sec-e-range').textContent =
    eSec.value_range || `${fmtL(valueMin)} – ${fmtL(valueMax)}`;
  setText('sec-e-content', eSec.content || secs.value_opinion || '');

  // Section F — risk points
  const fSec  = secs.F || {};
  const risks = fSec.risk_points || parseBullets(secs.risk_diligence || '');
  const list  = document.getElementById('sec-f-list');
  list.innerHTML = risks
    .filter(r => r.trim())
    .map(r => `<li><div class="risk-dot"></div><span>${r.replace(/^[•\-\*]\s*/,'')}</span></li>`)
    .join('');

  // Comparables
  const comps = report.comparables || [];
  if (comps.length > 0) {
    document.getElementById('comp-card').style.display = 'block';
    document.getElementById('comp-list').innerHTML = comps.map(c => `
      <div class="comp-item">
        <div>
          <div class="comp-desc">${c.description || ''}</div>
          <div class="comp-source">${c.source || ''}</div>
        </div>
        <div class="comp-price">${c.price_signal || ''}</div>
      </div>`).join('');
  }

  // Section G — disclaimer
  const gSec = secs.G || {};
  document.getElementById('sec-g').textContent =
    gSec.content || secs.disclaimer ||
    'This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation.';
}


// ─── Demo mode (no backend) ──────────────────────────────────────

function renderDemoReport() {
  const search = getSearch();
  const city   = search.city || 'Chennai';
  const loc    = search.locality || 'Anna Nagar';

  const demoData = getDemoData(search);

  renderReport(
    demoData.report,
    demoData.value_min,
    demoData.value_max,
    demoData.confidence,
    0
  );
}

function getDemoData(search) {
  const loc    = search.locality || 'Anna Nagar';
  const city   = search.city || 'Chennai';
  const type   = search.type || 'Apartment';
  const bhk    = search.bhk || '2BHK';

  // Approximate ranges by type
  const ranges = {
    Apartment:       [48, 74], IndependentHouse: [280, 420],
    Villa:           [380, 560], LandPlot:       [60, 95],
  };
  const [lo, hi] = ranges[type] || [48, 74];

  return {
    value_min:  lo, value_max: hi, confidence: 78,
    report: {
      sections: {
        A: { content: `This ${type.replace('IndependentHouse','Independent House')} is located in ${loc}, ${city}. ${search.carpetArea ? 'Carpet area: ' + search.carpetArea + ' sq.ft.' : ''} ${search.bhk ? 'Configuration: ' + bhk + '.' : ''} The locality is well-established with good connectivity and civic infrastructure.` },
        B: { content: `${loc} is a mature residential micro-market in ${city}, characterised by strong end-user demand and steady appreciation. Key demand drivers include metro connectivity, reputed schools, and proximity to commercial hubs.` },
        C: {
          land_rate_range: city === 'Bangalore' ? '₹12,000–₹22,000/sq.ft' : '₹10,000–₹18,000/sq.ft',
          apt_rate_range:  city === 'Bangalore' ? '₹7,000–₹11,000/sq.ft'  : '₹6,500–₹10,000/sq.ft',
          guideline_value: city === 'Bangalore' ? '₹5,500–₹8,000/sq.ft'   : '₹4,500–₹7,500/sq.ft',
          content: `Land rates in ${loc} are supported by strong demand from both end-users and investors. Government guideline values remain well below market rates, indicating active appreciation.`,
        },
        D: {
          land_value:    `${fmtL(Math.round(lo * 0.72))} – ${fmtL(Math.round(hi * 0.72))}`,
          building_value:`${fmtL(Math.round(lo * 0.20))} – ${fmtL(Math.round(hi * 0.20))}`,
          adjustments:   `+${fmtL(Math.round(lo * 0.08))} – +${fmtL(Math.round(hi * 0.08))}`,
          content: `Valuation is land-led for this property type. Building value uses age-adjusted depreciation. Location adjustments reflect road width, connectivity, and floor premium.`,
        },
        E: {
          value_range: `${fmtL(Math.round(lo * 1.02))} – ${fmtL(Math.round(hi * 0.98))}`,
          content: `Based on land-led valuation, locality benchmarks, and comparable pricing signals, the estimated market value is in the above range excluding registration charges and taxes.`,
        },
        F: {
          risk_points: [
            'Verify title deed, encumbrance certificate, and chain of ownership before transacting.',
            'Confirm building/layout approval (CMDA/DTCP) and obtain occupancy certificate.',
            'Inspect physical condition — this report assumes standard construction quality.',
            'Verify property tax payments up to date and no pending disputes.',
            'For apartments: confirm maintenance dues, share certificate, and society NOC.',
          ],
        },
        G: {
          content: 'This AI-generated valuation is for informational and decision-support purposes only. It does not constitute a statutory, bank-certified, or RERA-approved valuation. Always conduct independent legal and technical due diligence before transacting.',
        },
      },
      comparables: [
        { description: `Similar ${type === 'Apartment' ? '2 BHK apartment' : 'property'} in ${loc}`, price_signal: `${fmtL(Math.round(lo * 0.95))} – ${fmtL(Math.round(lo * 1.05))}`, source: 'Locality database' },
        { description: `Comparable listing, ${loc} adjacent area`, price_signal: `${fmtL(Math.round(hi * 0.92))} – ${fmtL(Math.round(hi * 1.00))}`, source: 'Locality database' },
        { description: `Government guideline value reference`, price_signal: city === 'Bangalore' ? '₹5,500–₹8,000/sq.ft' : '₹4,500–₹7,500/sq.ft', source: 'State Registration Dept. 2024' },
      ],
    },
  };
}


// ─── Helpers ─────────────────────────────────────────────────────

function fmtL(lakhs) {
  if (!lakhs && lakhs !== 0) return '—';
  if (lakhs >= 100) return `₹${(lakhs/100).toFixed(2)} Cr`;
  return `₹${lakhs} L`;
}

function confLabel(c) {
  if (c >= 80) return 'Good';
  if (c >= 65) return 'Moderate';
  return 'Low';
}

function confClass(c) {
  if (c >= 70) return 'confidence-high';
  if (c >= 50) return 'confidence-medium';
  return 'confidence-low';
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text || '';
}

function buildTable(id, rows) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = rows
    .filter(([, v]) => v)
    .map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`)
    .join('');
}

function parseBullets(text) {
  if (!text) return [];
  return text.split('\n').map(l => l.replace(/^[•\-\*]\s*/, '').trim()).filter(Boolean);
}

function showError(msg) {
  document.getElementById('report-loading').innerHTML = `
    <div style="max-width:420px;margin:0 auto;text-align:center;padding:60px 20px;">
      <div style="font-size:40px;margin-bottom:16px;">⚠️</div>
      <h2 style="font-family:var(--font-head);font-size:18px;margin-bottom:10px;">Report generation issue</h2>
      <p style="font-size:14px;color:var(--muted);">${msg}</p>
    </div>`;
}

function shareReport() {
  const search = getSearch();
  const text   = `My ValUprop property estimate for ${search.locality || 'my property'}: ${document.getElementById('r-value')?.textContent || ''}. Get yours at valuprop.in`;
  if (navigator.share) {
    navigator.share({ title: 'ValUprop Property Estimate', text }).catch(() => {});
  } else {
    navigator.clipboard.writeText(text).then(() => alert('Report summary copied to clipboard!'));
  }
}

function downloadPdf() {
  const paidValId = sessionStorage.getItem('valuprop_paid_val_id');
  const btn = document.getElementById('btn-download');

  if (!paidValId) {
    window.print();  // Fallback to browser print
    return;
  }

  if (btn) { btn.textContent = '⏳ Preparing…'; btn.disabled = true; }

  // OWASP A01 — PDF endpoint requires token. <a> downloads can't set headers,
  // so we use the ?token=... query form. Token never appears in browser history
  // (downloads don't go into navigation history).
  const token = sessionStorage.getItem('valuprop_paid_access_token') || '';
  const url = `${BACKEND_URL}/api/report/${paidValId}/pdf`
            + (token ? `?token=${encodeURIComponent(token)}` : '');
  const a   = document.createElement('a');
  a.href    = url;
  a.download= `ValUprop-Report-VUP-${String(paidValId).padStart(5,'0')}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  setTimeout(() => {
    if (btn) { btn.textContent = '⬇ Download PDF'; btn.disabled = false; }
  }, 3000);
}
