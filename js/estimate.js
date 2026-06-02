/**
 * ValUprop.in — Estimate Flow JS
 * js/estimate.js
 *
 * Handles: property type selection, dynamic forms,
 * address autocomplete (local), session storage, form submission
 */

/* ─── Address Data (locality suggestions) ─────────────────────── */
const LOCALITIES = [
  // ── Chennai — Central / Premium ─────────────────────────────
  { label: 'Anna Nagar, Chennai',         city: 'Chennai',   pincode: '600040' },
  { label: 'Anna Nagar West, Chennai',    city: 'Chennai',   pincode: '600101' },
  { label: 'T. Nagar, Chennai',           city: 'Chennai',   pincode: '600017' },
  { label: 'Nungambakkam, Chennai',       city: 'Chennai',   pincode: '600034' },
  { label: 'Kilpauk, Chennai',            city: 'Chennai',   pincode: '600010' },
  { label: 'Shenoy Nagar, Chennai',       city: 'Chennai',   pincode: '600030' },
  { label: 'Egmore, Chennai',             city: 'Chennai',   pincode: '600008' },
  { label: 'Triplicane, Chennai',         city: 'Chennai',   pincode: '600005' },
  { label: 'Royapettah, Chennai',         city: 'Chennai',   pincode: '600014' },
  { label: 'Alwarpet, Chennai',           city: 'Chennai',   pincode: '600018' },
  { label: 'Mylapore, Chennai',           city: 'Chennai',   pincode: '600004' },
  { label: 'Teynampet, Chennai',          city: 'Chennai',   pincode: '600086' },
  { label: 'R.A. Puram, Chennai',         city: 'Chennai',   pincode: '600028' },
  { label: 'Boat Club Road, Chennai',     city: 'Chennai',   pincode: '600028' },
  { label: 'Mandaveli, Chennai',          city: 'Chennai',   pincode: '600028' },
  { label: 'Aminjikarai, Chennai',        city: 'Chennai',   pincode: '600029' },
  // ── Chennai — South / Coastal ───────────────────────────────
  { label: 'Adyar, Chennai',              city: 'Chennai',   pincode: '600020' },
  { label: 'Kotturpuram, Chennai',        city: 'Chennai',   pincode: '600085' },
  { label: 'Saidapet, Chennai',           city: 'Chennai',   pincode: '600015' },
  { label: 'Thiruvanmiyur, Chennai',      city: 'Chennai',   pincode: '600041' },
  { label: 'Besant Nagar, Chennai',       city: 'Chennai',   pincode: '600090' },
  { label: 'Velachery, Chennai',          city: 'Chennai',   pincode: '600042' },
  { label: 'Ekkattuthangal, Chennai',     city: 'Chennai',   pincode: '600032' },
  { label: 'Nanganallur, Chennai',        city: 'Chennai',   pincode: '600061' },
  // ── Chennai — IT Corridor / OMR ─────────────────────────────
  { label: 'Perungudi, Chennai',          city: 'Chennai',   pincode: '600096' },
  { label: 'Thoraipakkam, Chennai',       city: 'Chennai',   pincode: '600097' },
  { label: 'Karapakkam, Chennai',         city: 'Chennai',   pincode: '600097' },
  { label: 'Sholinganallur, Chennai',     city: 'Chennai',   pincode: '600119' },
  { label: 'Navalur, Chennai',            city: 'Chennai',   pincode: '600130' },
  { label: 'Siruseri, Chennai',           city: 'Chennai',   pincode: '603103' },
  { label: 'Kelambakkam, Chennai',        city: 'Chennai',   pincode: '603103' },
  { label: 'Pallikaranai, Chennai',       city: 'Chennai',   pincode: '600100' },
  { label: 'Medavakkam, Chennai',         city: 'Chennai',   pincode: '600100' },
  // ── Chennai — West / Porur belt ─────────────────────────────
  { label: 'Porur, Chennai',              city: 'Chennai',   pincode: '600116' },
  { label: 'Manapakkam, Chennai',         city: 'Chennai',   pincode: '600125' },
  { label: 'Iyyappanthangal, Chennai',    city: 'Chennai',   pincode: '600056' },
  { label: 'Vadapalani, Chennai',         city: 'Chennai',   pincode: '600026' },
  { label: 'K.K. Nagar, Chennai',         city: 'Chennai',   pincode: '600078' },
  { label: 'Ashok Nagar, Chennai',        city: 'Chennai',   pincode: '600083' },
  { label: 'Mogappair, Chennai',          city: 'Chennai',   pincode: '600037' },
  { label: 'Valasaravakkam, Chennai',     city: 'Chennai',   pincode: '600087' },
  { label: 'Saligramam, Chennai',         city: 'Chennai',   pincode: '600093' },
  { label: 'Choolaimedu, Chennai',        city: 'Chennai',   pincode: '600094' },
  { label: 'Virugambakkam, Chennai',      city: 'Chennai',   pincode: '600092' },
  // ── Chennai — North / Outer ─────────────────────────────────
  { label: 'Perambur, Chennai',           city: 'Chennai',   pincode: '600011' },
  { label: 'Padi, Chennai',               city: 'Chennai',   pincode: '600050' },
  { label: 'Korattur, Chennai',           city: 'Chennai',   pincode: '600076' },
  { label: 'Ambattur, Chennai',           city: 'Chennai',   pincode: '600053' },
  { label: 'Avadi, Chennai',              city: 'Chennai',   pincode: '600054' },
  // ── Chennai — South Periphery / GST Road ────────────────────
  { label: 'Chromepet, Chennai',          city: 'Chennai',   pincode: '600044' },
  { label: 'Pallavaram, Chennai',         city: 'Chennai',   pincode: '600043' },
  { label: 'Tambaram, Chennai',           city: 'Chennai',   pincode: '600045' },
  { label: 'Selaiyur, Chennai',           city: 'Chennai',   pincode: '600073' },
  { label: 'Madambakkam, Chennai',        city: 'Chennai',   pincode: '600126' },
  { label: 'Urapakkam, Chennai',          city: 'Chennai',   pincode: '603210' },
  { label: 'Vandalur, Chennai',           city: 'Chennai',   pincode: '600048' },
  { label: 'Mudichur, Chennai',           city: 'Chennai',   pincode: '600048' },
  { label: 'Guduvanchery, Chennai',       city: 'Chennai',   pincode: '603202' },
  { label: 'Maraimalai Nagar, Chennai',   city: 'Chennai',   pincode: '603209' },

  // ── Bangalore — Central / Premium ───────────────────────────
  { label: 'Indiranagar, Bangalore',      city: 'Bangalore', pincode: '560038' },
  { label: 'Koramangala, Bangalore',      city: 'Bangalore', pincode: '560034' },
  { label: 'Jayanagar, Bangalore',        city: 'Bangalore', pincode: '560041' },
  { label: 'Sadashivanagar, Bangalore',   city: 'Bangalore', pincode: '560080' },
  { label: 'Malleshwaram, Bangalore',     city: 'Bangalore', pincode: '560003' },
  { label: 'Rajajinagar, Bangalore',      city: 'Bangalore', pincode: '560010' },
  { label: 'Frazer Town, Bangalore',      city: 'Bangalore', pincode: '560005' },
  { label: 'Cooke Town, Bangalore',       city: 'Bangalore', pincode: '560005' },
  { label: 'Richmond Town, Bangalore',    city: 'Bangalore', pincode: '560025' },
  { label: 'Lavelle Road, Bangalore',     city: 'Bangalore', pincode: '560001' },
  { label: 'Basavanagudi, Bangalore',     city: 'Bangalore', pincode: '560004' },
  // ── Bangalore — South ───────────────────────────────────────
  { label: 'JP Nagar, Bangalore',         city: 'Bangalore', pincode: '560078' },
  { label: 'BTM Layout, Bangalore',       city: 'Bangalore', pincode: '560076' },
  { label: 'HSR Layout, Bangalore',       city: 'Bangalore', pincode: '560102' },
  { label: 'Bannerghatta Road, Bangalore',city: 'Bangalore', pincode: '560076' },
  { label: 'Bommanahalli, Bangalore',     city: 'Bangalore', pincode: '560068' },
  { label: 'Begur, Bangalore',            city: 'Bangalore', pincode: '560068' },
  { label: 'Hulimavu, Bangalore',         city: 'Bangalore', pincode: '560076' },
  { label: 'Banashankari, Bangalore',     city: 'Bangalore', pincode: '560070' },
  { label: 'Vijayanagar, Bangalore',      city: 'Bangalore', pincode: '560040' },
  // ── Bangalore — East / IT Belt ──────────────────────────────
  { label: 'Whitefield, Bangalore',       city: 'Bangalore', pincode: '560066' },
  { label: 'Marathahalli, Bangalore',     city: 'Bangalore', pincode: '560037' },
  { label: 'Sarjapur Road, Bangalore',    city: 'Bangalore', pincode: '560035' },
  { label: 'Bellandur, Bangalore',        city: 'Bangalore', pincode: '560103' },
  { label: 'Doddanekundi, Bangalore',     city: 'Bangalore', pincode: '560037' },
  { label: 'Mahadevapura, Bangalore',     city: 'Bangalore', pincode: '560048' },
  { label: 'ITPL Main Road, Bangalore',   city: 'Bangalore', pincode: '560066' },
  { label: 'KR Puram, Bangalore',         city: 'Bangalore', pincode: '560036' },
  // ── Bangalore — North ───────────────────────────────────────
  { label: 'Hebbal, Bangalore',           city: 'Bangalore', pincode: '560024' },
  { label: 'Yelahanka, Bangalore',        city: 'Bangalore', pincode: '560064' },
  { label: 'Devanahalli, Bangalore',      city: 'Bangalore', pincode: '562110' },
  { label: 'Hennur, Bangalore',           city: 'Bangalore', pincode: '560043' },
  { label: 'Banaswadi, Bangalore',        city: 'Bangalore', pincode: '560043' },
  // ── Bangalore — South Periphery ─────────────────────────────
  { label: 'Electronic City, Bangalore',  city: 'Bangalore', pincode: '560100' },
];

/* ─── State ───────────────────────────────────────────────────── */
let selectedType  = null;
let selectedBhk   = null;
let selectedLocality = null;

/* ─── Step 1: Type Selection ──────────────────────────────────── */
function selectType(card) {
  document.querySelectorAll('.prop-type-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  selectedType = card.dataset.type;
  document.getElementById('step1-next').disabled = false;
}

function goToStep2() {
  if (!selectedType) return;
  const titles = {
    'Apartment':       'Apartment / Flat Details',
    'IndependentHouse':'Independent House Details',
    'Villa':           'Villa Details',
    'LandPlot':        'Land / Plot Details',
  };
  document.getElementById('step2-title').textContent = titles[selectedType] || 'Property Details';

  document.querySelectorAll('.prop-form-fields').forEach(f => f.style.display = 'none');
  const formMap = {
    'Apartment':       'form-apartment',
    'IndependentHouse':'form-house',
    'Villa':           'form-villa',
    'LandPlot':        'form-land',
  };
  const formEl = document.getElementById(formMap[selectedType]);
  if (formEl) formEl.style.display = 'block';

  showStep(2);
}

function goToStep1() { showStep(1); }

function showStep(n) {
  document.querySelectorAll('.form-step').forEach(s => s.classList.remove('active'));
  document.getElementById('step-' + n).classList.add('active');
  [1, 2, 3].forEach(i => {
    const el = document.getElementById('ps-' + i);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ─── Address autocomplete (Set 2 #6: suggestions only, free text allowed) ─ */
function handleAddressInput(input) {
  const query = input.value.trim().toLowerCase();
  const suggestBox = document.getElementById('address-suggestions');
  suggestBox.innerHTML = '';

  // Free text: typing invalidates any earlier selection unless user re-picks
  selectedLocality = null;

  if (query.length < 1) { suggestBox.style.display = 'none'; return; }

  const matches = LOCALITIES.filter(l =>
    l.label.toLowerCase().includes(query)
  ).slice(0, 8);

  if (matches.length === 0) { suggestBox.style.display = 'none'; return; }

  suggestBox.style.display = 'block';
  matches.forEach(loc => {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    div.textContent = loc.label;
    div.onclick = () => {
      input.value = loc.label;
      document.getElementById('f-pincode').value = loc.pincode;
      selectedLocality = loc;
      suggestBox.style.display = 'none';
    };
    suggestBox.appendChild(div);
  });
}

document.addEventListener('click', (e) => {
  const box = document.getElementById('address-suggestions');
  if (box && !box.contains(e.target) && e.target.id !== 'f-address') {
    box.style.display = 'none';
  }
});

/* ─── BHK selection ───────────────────────────────────────────── */
function selectBhk(btn) {
  document.querySelectorAll('.bhk-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  selectedBhk = btn.dataset.val;
  const hidden = document.getElementById('f-bhk');
  if (hidden) hidden.value = selectedBhk;
}

/* ─── Free-text city detection (Set 2 #6) ─────────────────────────
 * When the user types freely without picking a suggestion, do our best
 * to extract city and locality from the typed string. Defaults to Chennai. */
function detectCity(address) {
  const lower = (address || '').toLowerCase();
  if (lower.includes('bangalore') || lower.includes('bengaluru')) return 'Bangalore';
  // Allow inferring city from a known locality typed without city suffix
  for (const loc of LOCALITIES) {
    const locality = loc.label.split(',')[0].trim().toLowerCase();
    if (lower.includes(locality)) return loc.city;
  }
  return 'Chennai';
}

function extractLocality(address) {
  // If the user typed "<street>, <locality>, <city>" we want the middle part.
  // If they typed "<locality>, <city>" we want the first part.
  // If they typed a single token, return as-is.
  if (!address) return '';
  const parts = address.split(',').map(p => p.trim()).filter(Boolean);
  if (parts.length >= 3) return parts[parts.length - 2];   // "<...>, Locality, City"
  if (parts.length === 2) return parts[0];                  // "Locality, City"
  return parts[0] || '';
}

/* ─── Form submission ─────────────────────────────────────────── */
function submitForm() {
  const address = document.getElementById('f-address')?.value?.trim();
  const pincode = document.getElementById('f-pincode')?.value?.trim();

  if (!address) { alert('Please enter a property location.'); return; }
  if (!pincode) { alert('Please enter a pincode.'); return; }

  if (selectedType === 'Apartment') {
    if (!selectedBhk) { alert('Please select BHK configuration.'); return; }
    if (!document.getElementById('f-carpet')?.value) { alert('Please enter carpet area.'); return; }
    if (!document.getElementById('f-age-apt')?.value) { alert('Please select building age.'); return; }
  } else if (selectedType === 'IndependentHouse') {
    if (!document.getElementById('f-plot-house')?.value) { alert('Please enter plot area.'); return; }
    if (!document.getElementById('f-builtup-house')?.value) { alert('Please enter built-up area.'); return; }
    if (!document.getElementById('f-age-house')?.value) { alert('Please enter age of construction.'); return; }
  } else if (selectedType === 'Villa') {
    if (!document.getElementById('f-plot-villa')?.value) { alert('Please enter plot area.'); return; }
    if (!document.getElementById('f-builtup-villa')?.value) { alert('Please enter built-up area.'); return; }
    if (!document.getElementById('f-config-villa')?.value) { alert('Please select villa configuration.'); return; }
  } else if (selectedType === 'LandPlot') {
    if (!document.getElementById('f-plot-land')?.value) { alert('Please enter plot area.'); return; }
    if (!document.getElementById('f-landuse')?.value) { alert('Please select land use.'); return; }
    if (!document.getElementById('f-approval')?.value) { alert('Please select approval status.'); return; }
  }

  // Build search object — free-text friendly. If user picked a suggestion,
  // use its city/label. Otherwise infer from typed address.
  const inferredCity     = selectedLocality?.city || detectCity(address);
  const inferredLocality = selectedLocality?.label?.split(',')[0]?.trim()
                            || extractLocality(address);

  const search = {
    type:      selectedType,
    address:   address,
    city:      inferredCity,
    locality:  inferredLocality,
    pincode:   pincode,
    propName:  document.getElementById('f-propname')?.value || '',
    bhk:       selectedBhk || '',
    carpetArea:    document.getElementById('f-carpet')?.value || '',
    builtupArea:   document.getElementById('f-builtup')?.value || '',
    superBuiltup:  document.getElementById('f-superbuiltup')?.value || '',
    floorInfo:     document.getElementById('f-floor')?.value || '',
    ageApt:        document.getElementById('f-age-apt')?.value || '',
    furnishing:    document.getElementById('f-furnish')?.value || '',
    parkingApt:    document.getElementById('f-parking-apt')?.value || '',
    facing:        document.getElementById('f-facing')?.value || '',
    plotHouse:     document.getElementById('f-plot-house')?.value || '',
    builtupHouse:  document.getElementById('f-builtup-house')?.value || '',
    floorsHouse:   document.getElementById('f-floors-house')?.value || '',
    bedroomsHouse: document.getElementById('f-bedrooms-house')?.value || '',
    ageHouse:      document.getElementById('f-age-house')?.value || '',
    roadHouse:     document.getElementById('f-road-house')?.value || '',
    communityHouse:document.getElementById('f-community-house')?.value || '',
    parkingHouse:  document.getElementById('f-parking-house')?.value || '',
    plotVilla:     document.getElementById('f-plot-villa')?.value || '',
    builtupVilla:  document.getElementById('f-builtup-villa')?.value || '',
    configVilla:   document.getElementById('f-config-villa')?.value || '',
    ageVilla:      document.getElementById('f-age-villa')?.value || '',
    communityVilla:document.getElementById('f-community-villa')?.value || '',
    amenitiesVilla:document.getElementById('f-amenities-villa')?.value || '',
    plotLand:      document.getElementById('f-plot-land')?.value || '',
    landUse:       document.getElementById('f-landuse')?.value || '',
    approval:      document.getElementById('f-approval')?.value || '',
    roadLand:      document.getElementById('f-road-land')?.value || '',
    cornerPlot:    document.getElementById('f-corner')?.value || '',
    submittedAt: new Date().toISOString(),
  };

  sessionStorage.setItem('valuprop_search', JSON.stringify(search));
  window.location.href = 'loading.html';
}

/* ─── Shared: get search from session ────────────────────────── */
function getSearch() {
  try { return JSON.parse(sessionStorage.getItem('valuprop_search') || '{}'); }
  catch (e) { return {}; }
}

function markPaid(phone, email) {
  sessionStorage.setItem('valuprop_paid', '1');
  sessionStorage.setItem('valuprop_phone', phone);
  sessionStorage.setItem('valuprop_email', email);
}

function isPaid() { return sessionStorage.getItem('valuprop_paid') === '1'; }
