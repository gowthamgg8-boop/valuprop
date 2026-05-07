/**
 * ValUprop.in — Results Page JS (Phase 2 + Aggressive Preview)
 * Polls backend for LLM estimate. Falls back to static data if offline.
 * Renders an aggressive A–F preview using PRICE_DB to drive ₹99 conversion.
 */

const BACKEND_URL = window.BACKEND_URL || 'https://valuprop-api.onrender.com';
let _poll = 0;

const PRICE_DB = {
  Chennai: {
    'Anna Nagar':     {apt:[48,74],  house:[220,340],villa:[380,560],land:[95,140], trend:'+6.2%',sqft:4850},
    'T. Nagar':       {apt:[55,88],  house:[280,420],villa:[450,680],land:[110,165],trend:'+7.5%',sqft:5200},
    'Velachery':      {apt:[38,60],  house:[160,240],villa:[280,420],land:[70,105], trend:'+8.8%',sqft:4100},
    'Adyar':          {apt:[60,95],  house:[310,470],villa:[520,780],land:[120,180],trend:'+4.8%',sqft:5400},
    'Porur':          {apt:[32,52],  house:[120,180],villa:[200,300],land:[55,82],  trend:'+10.2%',sqft:3700},
    'Perambur':       {apt:[26,44],  house:[100,150],villa:[180,270],land:[45,68],  trend:'+11.8%',sqft:3200},
    'Chromepet':      {apt:[28,46],  house:[105,158],villa:[185,280],land:[48,72],  trend:'+11.3%',sqft:3400},
    'Tambaram':       {apt:[24,40],  house:[90,135], villa:[160,240],land:[40,60],  trend:'+12.6%',sqft:3100},
    'Sholinganallur': {apt:[44,68],  house:[185,278],villa:[310,465],land:[80,120], trend:'+9.4%', sqft:4400},
    'Pallavaram':     {apt:[27,45],  house:[102,153],villa:[180,270],land:[46,70],  trend:'+10.8%',sqft:3300},
    'Shenoy Nagar':   {apt:[60,95],  house:[420,520],villa:[580,800],land:[130,200],trend:'+5.5%', sqft:5600},
    'Mylapore':       {apt:[55,85],  house:[290,440],villa:[480,720],land:[115,175],trend:'+5.0%', sqft:5100},
    'Nungambakkam':   {apt:[65,105], house:[380,570],villa:[600,900],land:[140,210],trend:'+4.5%', sqft:5800},
    'Mogappair':      {apt:[35,58],  house:[155,232],villa:[270,405],land:[65,98],  trend:'+9.1%', sqft:4200},
    'Kilpauk':        {apt:[50,80],  house:[245,368],villa:[420,630],land:[105,158],trend:'+6.0%', sqft:4800},
  },
  Bangalore: {
    'Koramangala':    {apt:[70,110], house:[380,570],villa:[650,975], land:[160,240],trend:'+9.8%', sqft:6100},
    'Whitefield':     {apt:[52,85],  house:[240,360],villa:[420,630], land:[110,165],trend:'+12.2%',sqft:5200},
    'Indiranagar':    {apt:[75,118], house:[420,630],villa:[720,1080],land:[175,265],trend:'+8.4%', sqft:6300},
    'Jayanagar':      {apt:[65,102], house:[320,480],villa:[560,840], land:[140,210],trend:'+7.4%', sqft:5700},
    'HSR Layout':     {apt:[60,96],  house:[280,420],villa:[490,735], land:[130,195],trend:'+10.9%',sqft:5500},
    'Marathahalli':   {apt:[45,72],  house:[200,300],villa:[350,525], land:[95,143], trend:'+13.5%',sqft:4700},
    'BTM Layout':     {apt:[48,78],  house:[210,315],villa:[370,555], land:[100,150],trend:'+12.1%',sqft:4900},
    'Electronic City':{apt:[35,58],  house:[160,240],villa:[280,420], land:[75,113], trend:'+15.0%',sqft:4200},
    'Yelahanka':      {apt:[38,62],  house:[170,255],villa:[300,450], land:[82,123], trend:'+14.2%',sqft:4300},
    'Hebbal':         {apt:[56,90],  house:[260,390],villa:[460,690], land:[120,180],trend:'+11.3%',sqft:5300},
  }
};

/* Locality tier classification — drives section B narrative */
const LOCALITY_TIER = {
  // Premium / mature
  'Adyar':'premium', 'Nungambakkam':'premium', 'Mylapore':'premium', 'Shenoy Nagar':'premium',
  'T. Nagar':'premium', 'Kilpauk':'premium',
  'Indiranagar':'premium', 'Koramangala':'premium', 'Jayanagar':'premium',
  // Established
  'Anna Nagar':'established', 'Velachery':'established', 'Mogappair':'established',
  'HSR Layout':'established', 'Hebbal':'established', 'BTM Layout':'established',
  // Emerging / growth
  'Porur':'emerging', 'Sholinganallur':'emerging',
  'Whitefield':'emerging', 'Marathahalli':'emerging',
  // High-growth peripheral
  'Perambur':'peripheral', 'Chromepet':'peripheral', 'Tambaram':'peripheral', 'Pallavaram':'peripheral',
  'Electronic City':'peripheral', 'Yelahanka':'peripheral'
};

/* Type-specific generic risk points (1 shown free, rest blurred) */
const RISK_PREVIEW = {
  Apartment: [
    'Verify builder approvals (CMDA/DTCP/BDA) and Occupancy Certificate before purchase.',
    'Check society maintenance dues and corpus fund position.',
    'Confirm undivided share of land (UDS) matches sale agreement.',
    'Review parent document chain — minimum 30 years recommended.',
    'Verify no pending property tax or encumbrances on EC.'
  ],
  IndependentHouse: [
    'Verify patta/khata is in seller\'s name and matches sale deed.',
    'Confirm boundary measurements match registered documents.',
    'Check for building plan approval and deviation status.',
    'Review encumbrance certificate for last 30 years.',
    'Verify no overhead high-tension lines or setback violations.'
  ],
  Villa: [
    'Verify gated community RERA registration and approvals.',
    'Check association maintenance corpus and recurring charges.',
    'Confirm individual patta is granted (not just super-built share).',
    'Review parent document chain and conversion certificate.',
    'Verify amenities are completed — not just promised in brochure.'
  ],
  LandPlot: [
    'Verify DTCP/CMDA approval — unapproved layouts carry major risk.',
    'Confirm patta is in seller\'s name with current survey number.',
    'Check land use classification — agricultural vs residential.',
    'Review 30-year encumbrance certificate for any liens.',
    'Verify access road width and right-of-way documentation.'
  ]
};

document.addEventListener('DOMContentLoaded', function () {
  const search = getSearch();
  if (!search.type) { window.location.href = 'estimate.html'; return; }

  const typeLabels = {'Apartment':'Apartment','IndependentHouse':'Independent House','Villa':'Villa','LandPlot':'Land / Plot'};
  document.getElementById('res-type-badge').textContent = typeLabels[search.type] || search.type;
  document.getElementById('res-address').textContent    = search.address || search.locality;

  // Render the preview immediately — independent of backend
  renderPreview(search);

  const valId = sessionStorage.getItem('valuprop_val_id');
  if (valId) {
    pollFree(parseInt(valId), search);
  } else {
    trySubmitBackend(search);
  }
});

async function trySubmitBackend(search) {
  try {
    const r = await fetch(`${BACKEND_URL}/api/property/submit`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(search)
    });
    const d = await r.json();
    sessionStorage.setItem('valuprop_prop_id', d.property_id);
    sessionStorage.setItem('valuprop_val_id',  d.valuation_id);
    pollFree(d.valuation_id, search);
  } catch(e) { renderStatic(search); }
}

async function pollFree(valId, search) {
  try {
    const r = await fetch(`${BACKEND_URL}/api/valuation/free/${valId}`);
    const d = await r.json();
    if (d.status === 'pending') {
      if (++_poll >= 25) { renderStatic(search); return; }
      setTimeout(() => pollFree(valId, search), 2000);
      return;
    }
    if (d.status === 'ready') {
      render(d.value_min, d.value_max, d.insight, search);
    } else { renderStatic(search); }
  } catch(e) { renderStatic(search); }
}

function renderStatic(search) {
  const city = search.city||'Chennai';
  const loc  = search.locality||'Anna Nagar';
  const db   = (PRICE_DB[city]||{})[loc] || PRICE_DB.Chennai['Anna Nagar'];
  const bhkM = {'1BHK':0.58,'2BHK':1.0,'3BHK':1.45,'4BHK':1.9,'5BHK+':2.4};
  let lo,hi;
  if(search.type==='Apartment'){
    [lo,hi]=db.apt; const m=bhkM[search.bhk]||1;
    lo=Math.round(lo*m); hi=Math.round(hi*m);
    if(search.carpetArea){const a=parseInt(search.carpetArea),r=db.sqft;lo=Math.round((lo+a*r*0.9/1e5)/2);hi=Math.round((hi+a*r*1.1/1e5)/2);}
  }else if(search.type==='IndependentHouse'){
    [lo,hi]=db.house;
    if(search.plotHouse){const a=parseInt(search.plotHouse),r=db.sqft*1.4;lo=Math.round(a*r*0.85/1e5);hi=Math.round(a*r*1.15/1e5);}
  }else if(search.type==='Villa'){[lo,hi]=db.villa;
  }else{[lo,hi]=db.land;
    if(search.plotLand){const a=parseInt(search.plotLand),r=db.sqft*1.2;lo=Math.round(a*r*0.85/1e5);hi=Math.round(a*r*1.15/1e5);}
  }
  const teasers={
    Apartment:`Apartments in this locality have seen ${db.trend} price appreciation in the last 12 months.`,
    IndependentHouse:`Independent houses here are land-led. Plot rates at ₹${Math.round(db.sqft*1.4).toLocaleString('en-IN')}/sq.ft.`,
    Villa:`Villas command a 20–35% premium over regular apartments due to gated community amenities.`,
    LandPlot:`Land in this area has appreciated ${db.trend} in 12 months. DTCP/CMDA plots command highest premiums.`,
  };
  render(lo, hi, teasers[search.type]||teasers.Apartment, search);
}

function render(lo, hi, insight, search) {
  document.getElementById('res-value-range').textContent = `${fmt(lo)} \u2013 ${fmt(hi)}`;
  document.getElementById('teaser-text').textContent = insight||'';
  const el = document.getElementById('preview-asset');
  if(el) el.textContent = buildAssetLine(search);
}

function fmt(l) {
  if(!l && l!==0) return '\u2014';
  return l>=100 ? `\u20b9${(l/100).toFixed(2)} Cr` : `\u20b9${l} L`;
}

function buildAssetLine(s) {
  const tl={'Apartment':'Apartment','IndependentHouse':'Indep. House','Villa':'Villa','LandPlot':'Land / Plot'};
  const p=[tl[s.type]||s.type];
  if(s.bhk) p.push(s.bhk.replace('BHK',' BHK'));
  if(s.carpetArea) p.push(s.carpetArea+' sq.ft');
  if(s.plotHouse)  p.push('Plot: '+s.plotHouse+' sq.ft');
  if(s.plotLand)   p.push(s.plotLand+' sq.ft');
  p.push(s.locality||s.address);
  return p.join(' \u00b7 ');
}

/* ============================================================
   PREVIEW RENDERING (A through F)
   All data is computed client-side from PRICE_DB + user inputs.
   No extra backend calls; nothing leaks the paid LLM output.
   ============================================================ */
function renderPreview(search) {
  const city = search.city || 'Chennai';
  const loc  = search.locality || 'Anna Nagar';
  const db   = (PRICE_DB[city] || {})[loc] || PRICE_DB.Chennai['Anna Nagar'];
  const tier = LOCALITY_TIER[loc] || 'established';

  renderSectionA(search, db);
  renderSectionB(search, db, tier, loc, city);
  renderSectionC(search, db, loc);
  renderSectionD(search, db);
  renderSectionF(search);
}

/* A — Asset Overview: structured fact list */
function renderSectionA(s, db) {
  const typeLabel = {'Apartment':'Apartment','IndependentHouse':'Independent House','Villa':'Villa','LandPlot':'Land / Plot'}[s.type] || s.type;
  const facts = [];
  facts.push(['Property type', typeLabel]);
  if (s.bhk)         facts.push(['Configuration', s.bhk.replace('BHK',' BHK')]);
  if (s.carpetArea)  facts.push(['Carpet area', `${parseInt(s.carpetArea).toLocaleString('en-IN')} sq.ft`]);
  if (s.plotHouse)   facts.push(['Plot area', `${parseInt(s.plotHouse).toLocaleString('en-IN')} sq.ft`]);
  if (s.plotLand)    facts.push(['Plot area', `${parseInt(s.plotLand).toLocaleString('en-IN')} sq.ft`]);
  if (s.age)         facts.push(['Property age', `${s.age} years`]);
  if (s.parking)     facts.push(['Parking', s.parking]);
  facts.push(['Locality', `${s.locality || ''}, ${s.city || 'Chennai'}`]);

  const rows = facts.map(([k,v]) =>
    `<div class="rep-data-row"><span class="rep-data-label">${escapeHtml(k)}</span><span class="rep-data-value">${escapeHtml(v)}</span></div>`
  ).join('');

  document.getElementById('rep-a-body').innerHTML =
    `<p>The subject property is summarised below. These are the inputs your full report\u2019s valuation is built on.</p>
     <div class="rep-data-grid">${rows}</div>`;
}

/* B — Micro-Market Context: real narrative built from tier + trend */
function renderSectionB(s, db, tier, loc, city) {
  const trend = db.trend;
  const sqftRate = db.sqft.toLocaleString('en-IN');

  const tierNarrative = {
    premium: `${loc} is one of ${city}\u2019s most established premium pockets, characterised by mature infrastructure, established schools and hospitals, and a stable resident profile. Inventory turnover here is typically lower, with sellers commanding pricing power.`,
    established: `${loc} is a well-established residential micro-market in ${city} with mature infrastructure, strong rental demand, and a healthy mix of older standalone buildings and newer gated developments. Demand here is broad-based across families and working professionals.`,
    emerging: `${loc} is an actively emerging micro-market in ${city} \u2014 driven by IT/ITES employment hubs, ongoing infrastructure upgrades, and new gated developments coming online. This tier typically shows above-average price appreciation but also higher inventory churn.`,
    peripheral: `${loc} is a high-growth peripheral micro-market in ${city}, benefiting from metro/road connectivity expansion, new affordable-to-mid-segment supply, and outward demand spillover from inner suburbs. Appreciation potential here is among the highest in the city, paired with longer absorption timelines.`
  };

  const para1 = tierNarrative[tier] || tierNarrative.established;
  const para2 = `Locality benchmark land rate is approximately <strong>\u20b9${sqftRate}/sq.ft</strong>. Over the past 12 months, properties in this micro-market have moved <strong>${trend}</strong>, ${parseFloat(trend) > 8 ? 'meaningfully outperforming' : parseFloat(trend) > 5 ? 'tracking close to' : 'underperforming'} the broader ${city} residential index.`;

  document.getElementById('rep-b-body').innerHTML =
    `<p>${para1}</p><p>${para2}</p>`;
}

/* C — Observed Pricing Signals: real numbers from PRICE_DB */
function renderSectionC(s, db, loc) {
  const sqftRate = db.sqft;
  const rows = [];

  // Land rate (always shown)
  rows.push({
    label: 'Locality land rate',
    value: `\u20b9${sqftRate.toLocaleString('en-IN')}/sq.ft`,
    meta: 'Benchmark for sale transactions in this micro-market'
  });

  // Type-specific row
  if (s.type === 'Apartment') {
    const [lo, hi] = db.apt;
    rows.push({
      label: 'Apartment range (typical 2 BHK)',
      value: `\u20b9${lo} L \u2013 \u20b9${hi} L`,
      meta: 'Pre-adjustment for size, age and floor'
    });
  } else if (s.type === 'IndependentHouse') {
    const [lo, hi] = db.house;
    rows.push({
      label: 'Independent house range',
      value: `\u20b9${(lo/100).toFixed(2)} Cr \u2013 \u20b9${(hi/100).toFixed(2)} Cr`,
      meta: 'Typical built-up house on standard plot'
    });
  } else if (s.type === 'Villa') {
    const [lo, hi] = db.villa;
    rows.push({
      label: 'Villa range (gated community)',
      value: `\u20b9${(lo/100).toFixed(2)} Cr \u2013 \u20b9${(hi/100).toFixed(2)} Cr`,
      meta: 'Premium reflects amenities and clubhouse'
    });
  } else {
    const [lo, hi] = db.land;
    rows.push({
      label: 'Land/plot range',
      value: `\u20b9${lo} L \u2013 \u20b9${hi} L`,
      meta: 'Approved DTCP/CMDA plots, standard size'
    });
  }

  // 12-month trend
  rows.push({
    label: '12-month price trend',
    value: db.trend,
    meta: 'Year-on-year appreciation in this locality'
  });

  // Guideline value (estimated as ~55-65% of market in TN/KA, blurred — that's a real-report value)
  rows.push({
    label: 'Indicative guideline value',
    value: `<span class="rep-blur">\u20b9XX,XXX/sq.ft</span>`,
    meta: 'State-published rate \u2014 in your ₹99 report'
  });

  // Comparable transactions (blurred — paid)
  rows.push({
    label: 'Recent comparable transactions',
    value: `<span class="rep-blur">X comparables</span>`,
    meta: 'Sale-deed signals \u2014 in your ₹99 report'
  });

  const html = rows.map(r =>
    `<div class="rep-data-row">
       <div>
         <div class="rep-data-label">${r.label}</div>
         <div class="rep-data-meta">${r.meta}</div>
       </div>
       <div class="rep-data-value">${r.value}</div>
     </div>`
  ).join('');

  document.getElementById('rep-c-grid').innerHTML = html;
}

/* D — Valuation Build-Up: structure visible, component values blurred */
function renderSectionD(s, db) {
  // Show the methodology with one anchor value so the reader knows it's real,
  // then blur the component splits and the total.
  const isLandLed = s.type !== 'Apartment';
  let html = '';

  if (s.type === 'Apartment') {
    html = `
      <div class="rep-formula-row">
        <span class="rep-formula-label">Carpet area \u00d7 effective ₹/sq.ft</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X,XX,XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">+</span> Floor / view premium</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X,XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">+</span> Parking &amp; amenities adjustment</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">\u2212</span> Age depreciation${s.age ? ` (${s.age} yr)` : ''}</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9XX,XXX</span></span>
      </div>
      <div class="rep-formula-row is-total">
        <span class="rep-formula-label">Independent value (mid-point)</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X.XX Cr</span></span>
      </div>`;
  } else {
    // Land-led: show the real land-rate anchor, blur the rest
    const sqftRate = db.sqft.toLocaleString('en-IN');
    const plotLabel = s.plotHouse ? `${parseInt(s.plotHouse).toLocaleString('en-IN')} sq.ft` :
                      s.plotLand  ? `${parseInt(s.plotLand).toLocaleString('en-IN')} sq.ft`  : 'plot area';
    html = `
      <div class="rep-formula-row">
        <span class="rep-formula-label">Land component (${plotLabel} \u00d7 \u20b9${sqftRate}/sq.ft)</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X,XX,XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">+</span> Depreciated building value</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9XX,XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">+</span> Location / corner premium</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X,XX,XXX</span></span>
      </div>
      <div class="rep-formula-row">
        <span class="rep-formula-label"><span class="rep-formula-op">\u2212</span> Encumbrance / condition adjustment</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9XX,XXX</span></span>
      </div>
      <div class="rep-formula-row is-total">
        <span class="rep-formula-label">Independent value (mid-point)</span>
        <span class="rep-formula-val"><span class="rep-blur">\u20b9X.XX Cr</span></span>
      </div>`;
  }

  document.getElementById('rep-d-formula').innerHTML = html;
}

/* F — Risk & Due Diligence: 1 of 5 visible */
function renderSectionF(s) {
  const items = RISK_PREVIEW[s.type] || RISK_PREVIEW.Apartment;
  const html = items.map((txt, i) => {
    if (i === 0) {
      return `<li class="rep-risk-item">
                <span class="rep-risk-bullet">${i+1}</span>
                <span class="rep-risk-text">${escapeHtml(txt)}</span>
              </li>`;
    }
    return `<li class="rep-risk-item is-locked">
              <span class="rep-risk-bullet">${i+1}</span>
              <span class="rep-risk-text"><span class="rep-blur">${escapeHtml(txt)}</span></span>
            </li>`;
  }).join('');

  document.getElementById('rep-f-list').innerHTML = html;
}

/* tiny escape helper */
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function proceedToPayment() {
  const phone = document.getElementById('lcc-phone')?.value?.trim();
  const email = document.getElementById('lcc-email')?.value?.trim();
  const err   = document.getElementById('lcc-error');
  if(!phone||phone.replace(/\D/g,'').length<10){err.textContent='Please enter a valid 10-digit phone number.';return;}
  if(!email||!email.includes('@')){err.textContent='Please enter a valid email address.';return;}
  err.textContent='';
  const search=getSearch(); search.phone=phone; search.email=email;
  sessionStorage.setItem('valuprop_search',JSON.stringify(search));
  const propId=sessionStorage.getItem('valuprop_prop_id');
  if(propId){try{await fetch(`${BACKEND_URL}/api/lead/capture`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({property_id:parseInt(propId),phone,email})});}catch(e){}}
  window.location.href='payment.html';
}
