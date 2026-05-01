/**
 * ValUprop.in — Estimate Flow JS
 * js/estimate.js
 *
 * Handles: property type selection, dynamic forms,
 * address autocomplete (local), session storage, form submission
 */

/* ─── Address Data (locality suggestions) ─────────────────────── */
const LOCALITIES = [
  // Chennai
  { label: 'Anna Nagar, Chennai',        city: 'Chennai',   pincode: '600040' },
  { label: 'T. Nagar, Chennai',          city: 'Chennai',   pincode: '600017' },
  { label: 'Velachery, Chennai',         city: 'Chennai',   pincode: '600042' },
  { label: 'Adyar, Chennai',             city: 'Chennai',   pincode: '600020' },
  { label: 'Porur, Chennai',             city: 'Chennai',   pincode: '600116' },
  { label: 'Perambur, Chennai',          city: 'Chennai',   pincode: '600011' },
  { label: 'Chromepet, Chennai',         city: 'Chennai',   pincode: '600044' },
  { label: 'Tambaram, Chennai',          city: 'Chennai',   pincode: '600045' },
  { label: 'Sholinganallur, Chennai',    city: 'Chennai',   pincode: '600119' },
  { label: 'Pallavaram, Chennai',        city: 'Chennai',   pincode: '600043' },
  { label: 'Mogappair, Chennai',         city: 'Chennai',   pincode: '600037' },
  { label: 'Nungambakkam, Chennai',      city: 'Chennai',   pincode: '600034' },
  { label: 'Kilpauk, Chennai',           city: 'Chennai',   pincode: '600010' },
  { label: 'Shenoy Nagar, Chennai',      city: 'Chennai',   pincode: '600030' },
  { label: 'Mylapore, Chennai',          city: 'Chennai',   pincode: '600004' },
  { label: 'Thiruvanmiyur, Chennai',     city: 'Chennai',   pincode: '600041' },
  { label: 'Medavakkam, Chennai',        city: 'Chennai',   pincode: '600100' },
  { label: 'Perungudi, Chennai',         city: 'Chennai',   pincode: '600096' },
  { label: 'Guduvanchery, Chennai',      city: 'Chennai',   pincode: '603202' },
  // Bangalore
  { label: 'Koramangala, Bangalore',     city: 'Bangalore', pincode: '560034' },
  { label: 'Whitefield, Bangalore',      city: 'Bangalore', pincode: '560066' },
  { label: 'Indiranagar, Bangalore',     city: 'Bangalore', pincode: '560038' },
  { label: 'Jayanagar, Bangalore',       city: 'Bangalore', pincode: '560041' },
  { label: 'HSR Layout, Bangalore',      city: 'Bangalore', pincode: '560102' },
  { label: 'Marathahalli, Bangalore',    city: 'Bangalore', pincode: '560037' },
  { label: 'BTM Layout, Bangalore',      city: 'Bangalore', pincode: '560076' },
  { label: 'Electronic City, Bangalore', city: 'Bangalore', pincode: '560100' },
  { label: 'Yelahanka, Bangalore',       city: 'Bangalore', pincode: '560064' },
  { label: 'Hebbal, Bangalore',          city: 'Bangalore', pincode: '560024' },
  { label: 'JP Nagar, Bangalore',        city: 'Bangalore', pincode: '560078' },
  { label: 'Sarjapur Road, Bangalore',   city: 'Bangalore', pincode: '560035' },
  { label: 'Bannerghatta Road, Bangalore',city: 'Bangalore', pincode: '560076' },
  { label: 'Rajajinagar, Bangalore',     city: 'Bangalore', pincode: '560010' },
  { label: 'Malleshwaram, Bangalore',    city: 'Bangalore', pincode: '560003' },
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
  // Update step 2 title
  const titles = {
    'Apartment':       'Apartment / Flat Details',
    'IndependentHouse':'Independent House Details',
    'Villa':           'Villa Details',
    'LandPlot':        'Land / Plot Details',
  };
  document.getElementById('step2-title').textContent = titles[selectedType] || 'Property Details';

  // Show correct form fields
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

/* ─── Address autocomplete ────────────────────────────────────── */
function handleAddressInput(input) {
  const query = input.value.trim().toLowerCase();
  const suggestBox = document.getElementById('address-suggestions');
  suggestBox.innerHTML = '';
  selectedLocality = null;

  if (query.length < 2) { suggestBox.style.display = 'none'; return; }

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

// Close suggestions on outside click
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

/* ─── Form submission ─────────────────────────────────────────── */
function submitForm() {
  // Validate required fields
  const address = document.getElementById('f-address')?.value?.trim();
  const pincode = document.getElementById('f-pincode')?.value?.trim();

  if (!address) { alert('Please enter a property location.'); return; }
  if (!pincode) { alert('Please enter a pincode.'); return; }

  // Type-specific validation
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

  // Build search object
  const search = {
    type:      selectedType,
    address:   address,
    city:      selectedLocality?.city || detectCity(address),
    locality:  selectedLocality?.label?.split(',')[0]?.trim() || address.split(',')[0]?.trim(),
    pincode:   pincode,
    propName:  document.getElementById('f-propname')?.value || '',
    bhk:       selectedBhk || '',
    // Apartment
    carpetArea:    document.getElementById('f-carpet')?.value || '',
    builtupArea:   document.getElementById('f-builtup')?.value || '',
    superBuiltup:  document.getElementById('f-superbuiltup')?.value || '',
    floorInfo:     document.getElementById('f-floor')?.value || '',
    ageApt:        document.getElementById('f-age-apt')?.value || '',
    furnishing:    document.getElementById('f-furnish')?.value || '',
    parkingApt:    document.getElementById('f-parking-apt')?.value || '',
    facing:        document.getElementById('f-facing')?.value || '',
    // House
    plotHouse:     document.getElementById('f-plot-house')?.value || '',
    builtupHouse:  document.getElementById('f-builtup-house')?.value || '',
    floorsHouse:   document.getElementById('f-floors-house')?.value || '',
    bedroomsHouse: document.getElementById('f-bedrooms-house')?.value || '',
    ageHouse:      document.getElementById('f-age-house')?.value || '',
    roadHouse:     document.getElementById('f-road-house')?.value || '',
    communityHouse:document.getElementById('f-community-house')?.value || '',
    parkingHouse:  document.getElementById('f-parking-house')?.value || '',
    // Villa
    plotVilla:     document.getElementById('f-plot-villa')?.value || '',
    builtupVilla:  document.getElementById('f-builtup-villa')?.value || '',
    configVilla:   document.getElementById('f-config-villa')?.value || '',
    ageVilla:      document.getElementById('f-age-villa')?.value || '',
    communityVilla:document.getElementById('f-community-villa')?.value || '',
    amenitiesVilla:document.getElementById('f-amenities-villa')?.value || '',
    // Land
    plotLand:      document.getElementById('f-plot-land')?.value || '',
    landUse:       document.getElementById('f-landuse')?.value || '',
    approval:      document.getElementById('f-approval')?.value || '',
    roadLand:      document.getElementById('f-road-land')?.value || '',
    cornerPlot:    document.getElementById('f-corner')?.value || '',
    // Meta
    submittedAt: new Date().toISOString(),
  };

  sessionStorage.setItem('valuprop_search', JSON.stringify(search));
  window.location.href = 'loading.html';
}

function detectCity(address) {
  const lower = address.toLowerCase();
  if (lower.includes('bangalore') || lower.includes('bengaluru')) return 'Bangalore';
  return 'Chennai';
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
