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

/* ─── Address Aliases ──────────────────────────────────────────
 * Common sub-locality / colony / landmark names users actually type.
 * Each alias points to a `parent` locality that MUST exist as a PRICE_DB
 * key in results.js. The `pincode` is the alias area's real pincode;
 * `parent` drives the rate lookup.
 *
 * When user picks an alias from autocomplete:
 *   - The alias label is shown in the address field
 *   - The alias's real pincode is auto-filled
 *   - The parent locality is used for PRICE_DB rate lookup
 *
 * Add new aliases here over time — common patterns:
 *   - Sub-pockets within a known locality (Shanti Colony → Anna Nagar)
 *   - Landmarks people search by (Pondy Bazaar → T. Nagar)
 *   - Roads / streets (Cathedral Road → Alwarpet)
 *   - Adjacent areas where rates are similar to a parent we have data for
 */
const LOCALITY_ALIASES = [
  // ── Chennai — Anna Nagar / North-central pockets ─────────────
  { label: 'Shanti Colony, Chennai',         parent: 'Anna Nagar',         city: 'Chennai',   pincode: '600040' },
  { label: 'Thirumangalam, Chennai',         parent: 'Anna Nagar',         city: 'Chennai',   pincode: '600040' },
  { label: 'Blue Cross Road, Chennai',       parent: 'Anna Nagar West',    city: 'Chennai',   pincode: '600101' },
  // ── Chennai — T. Nagar / commercial belt ────────────────────
  { label: 'Pondy Bazaar, Chennai',          parent: 'T. Nagar',           city: 'Chennai',   pincode: '600017' },
  { label: 'Panagal Park, Chennai',          parent: 'T. Nagar',           city: 'Chennai',   pincode: '600017' },
  { label: 'GN Chetty Road, Chennai',        parent: 'T. Nagar',           city: 'Chennai',   pincode: '600017' },
  { label: 'Usman Road, Chennai',            parent: 'T. Nagar',           city: 'Chennai',   pincode: '600017' },
  // ── Chennai — Nungambakkam / Alwarpet ───────────────────────
  { label: 'Sterling Road, Chennai',         parent: 'Nungambakkam',       city: 'Chennai',   pincode: '600034' },
  { label: 'Khader Nawaz Khan Road, Chennai',parent: 'Nungambakkam',       city: 'Chennai',   pincode: '600034' },
  { label: 'College Road, Chennai',          parent: 'Nungambakkam',       city: 'Chennai',   pincode: '600006' },
  { label: 'Cathedral Road, Chennai',        parent: 'Alwarpet',           city: 'Chennai',   pincode: '600018' },
  { label: 'TTK Road, Chennai',              parent: 'Alwarpet',           city: 'Chennai',   pincode: '600018' },
  { label: 'Eldams Road, Chennai',           parent: 'Alwarpet',           city: 'Chennai',   pincode: '600018' },
  // ── Chennai — Mylapore / Royapettah ─────────────────────────
  { label: 'Luz Corner, Chennai',            parent: 'Mylapore',           city: 'Chennai',   pincode: '600004' },
  { label: 'Royapettah High Road, Chennai',  parent: 'Royapettah',         city: 'Chennai',   pincode: '600014' },
  // ── Chennai — Adyar / South ─────────────────────────────────
  { label: 'Gandhi Mandapam Road, Chennai',  parent: 'Kotturpuram',        city: 'Chennai',   pincode: '600085' },
  { label: 'LB Road, Chennai',               parent: 'Adyar',              city: 'Chennai',   pincode: '600020' },
  { label: 'Lattice Bridge Road, Chennai',   parent: 'Adyar',              city: 'Chennai',   pincode: '600020' },
  { label: 'Sardar Patel Road, Chennai',     parent: 'Adyar',              city: 'Chennai',   pincode: '600020' },
  { label: 'Indira Nagar Adyar, Chennai',    parent: 'Adyar',              city: 'Chennai',   pincode: '600020' },
  { label: 'Kasturba Nagar, Chennai',        parent: 'Adyar',              city: 'Chennai',   pincode: '600020' },
  // ── Chennai — Besant Nagar / Thiruvanmiyur ─────────────────
  { label: 'Kalakshetra Colony, Chennai',    parent: 'Besant Nagar',       city: 'Chennai',   pincode: '600090' },
  { label: "Elliot's Beach, Chennai",        parent: 'Besant Nagar',       city: 'Chennai',   pincode: '600090' },
  { label: 'Elliots Beach Road, Chennai',    parent: 'Besant Nagar',       city: 'Chennai',   pincode: '600090' },
  { label: 'Valmiki Nagar, Chennai',         parent: 'Thiruvanmiyur',      city: 'Chennai',   pincode: '600041' },
  { label: 'Kapaleeshwarar Nagar, Chennai',  parent: 'Thiruvanmiyur',      city: 'Chennai',   pincode: '600115' },
  { label: 'Neelankarai, Chennai',           parent: 'Thiruvanmiyur',      city: 'Chennai',   pincode: '600115' },
  { label: 'Palavakkam, Chennai',            parent: 'Thiruvanmiyur',      city: 'Chennai',   pincode: '600041' },
  { label: 'Injambakkam, Chennai',           parent: 'Sholinganallur',     city: 'Chennai',   pincode: '600115' },
  { label: 'Akkarai, Chennai',               parent: 'Sholinganallur',     city: 'Chennai',   pincode: '600119' },
  { label: 'Uthandi, Chennai',               parent: 'Sholinganallur',     city: 'Chennai',   pincode: '600119' },
  { label: 'Taramani, Chennai',              parent: 'Velachery',          city: 'Chennai',   pincode: '600113' },
  // ── Chennai — Vadapalani / KK Nagar / Ashok Nagar belt ─────
  { label: '100 Feet Road Vadapalani, Chennai', parent: 'Vadapalani',      city: 'Chennai',   pincode: '600026' },
  { label: 'Forum Vadapalani, Chennai',      parent: 'Vadapalani',         city: 'Chennai',   pincode: '600026' },
  { label: 'Ashok Pillar, Chennai',          parent: 'Ashok Nagar',        city: 'Chennai',   pincode: '600083' },
  { label: 'MGR Nagar, Chennai',             parent: 'K.K. Nagar',         city: 'Chennai',   pincode: '600078' },
  { label: 'Nelson Manickam Road, Chennai',  parent: 'Aminjikarai',        city: 'Chennai',   pincode: '600029' },
  { label: 'Arumbakkam, Chennai',            parent: 'Aminjikarai',        city: 'Chennai',   pincode: '600106' },
  { label: 'Nerkundram, Chennai',            parent: 'Mogappair',          city: 'Chennai',   pincode: '600107' },
  // ── Chennai — Porur / West outskirts ────────────────────────
  { label: 'Mount-Poonamallee Road, Chennai',parent: 'Porur',              city: 'Chennai',   pincode: '600116' },
  { label: 'L&T Bypass, Chennai',            parent: 'Manapakkam',         city: 'Chennai',   pincode: '600125' },

  // ── Bangalore — Indiranagar / Koramangala / Jayanagar ──────
  { label: '100 Feet Road Indiranagar, Bangalore', parent: 'Indiranagar',  city: 'Bangalore', pincode: '560038' },
  { label: 'CMH Road, Bangalore',            parent: 'Indiranagar',        city: 'Bangalore', pincode: '560038' },
  { label: 'Old Madras Road, Bangalore',     parent: 'Indiranagar',        city: 'Bangalore', pincode: '560038' },
  { label: 'HAL 2nd Stage, Bangalore',       parent: 'Indiranagar',        city: 'Bangalore', pincode: '560008' },
  { label: 'Koramangala 1st Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560034' },
  { label: 'Koramangala 4th Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560034' },
  { label: 'Koramangala 5th Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560095' },
  { label: 'Koramangala 6th Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560095' },
  { label: 'Koramangala 7th Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560095' },
  { label: 'Koramangala 8th Block, Bangalore', parent: 'Koramangala',      city: 'Bangalore', pincode: '560095' },
  { label: 'Forum Mall Koramangala, Bangalore', parent: 'Koramangala',     city: 'Bangalore', pincode: '560095' },
  { label: 'Jayanagar 4th Block, Bangalore', parent: 'Jayanagar',          city: 'Bangalore', pincode: '560011' },
  { label: 'Jayanagar 7th Block, Bangalore', parent: 'Jayanagar',          city: 'Bangalore', pincode: '560070' },
  { label: 'Jayanagar 9th Block, Bangalore', parent: 'Jayanagar',          city: 'Bangalore', pincode: '560069' },
  // ── Bangalore — Sadashivanagar / Malleshwaram / Basavanagudi
  { label: 'Sankey Tank Road, Bangalore',    parent: 'Sadashivanagar',     city: 'Bangalore', pincode: '560080' },
  { label: 'Mekhri Circle, Bangalore',       parent: 'Sadashivanagar',     city: 'Bangalore', pincode: '560080' },
  { label: '8th Cross Malleshwaram, Bangalore', parent: 'Malleshwaram',    city: 'Bangalore', pincode: '560003' },
  { label: 'Gandhi Bazaar, Bangalore',       parent: 'Basavanagudi',       city: 'Bangalore', pincode: '560004' },
  { label: 'Hanumantha Nagar, Bangalore',    parent: 'Basavanagudi',       city: 'Bangalore', pincode: '560019' },
  // ── Bangalore — Central premium ─────────────────────────────
  { label: 'MG Road, Bangalore',             parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  { label: 'Brigade Road, Bangalore',        parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  { label: 'Church Street, Bangalore',       parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  { label: 'Vittal Mallya Road, Bangalore',  parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  { label: 'Cunningham Road, Bangalore',     parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560052' },
  { label: 'Infantry Road, Bangalore',       parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  { label: 'UB City, Bangalore',             parent: 'Lavelle Road',       city: 'Bangalore', pincode: '560001' },
  // ── Bangalore — East / IT belt ──────────────────────────────
  { label: 'ITPL, Bangalore',                parent: 'Whitefield',         city: 'Bangalore', pincode: '560066' },
  { label: 'Brookefield, Bangalore',         parent: 'Marathahalli',       city: 'Bangalore', pincode: '560037' },
  { label: 'Varthur, Bangalore',             parent: 'Bellandur',          city: 'Bangalore', pincode: '560087' },
  { label: 'Kadugodi, Bangalore',            parent: 'Whitefield',         city: 'Bangalore', pincode: '560067' },
  { label: 'Hoodi, Bangalore',               parent: 'Mahadevapura',       city: 'Bangalore', pincode: '560048' },
  { label: 'AECS Layout, Bangalore',         parent: 'Marathahalli',       city: 'Bangalore', pincode: '560037' },
  { label: 'Outer Ring Road Marathahalli, Bangalore', parent: 'Marathahalli', city: 'Bangalore', pincode: '560037' },
  { label: 'Kundalahalli, Bangalore',        parent: 'Marathahalli',       city: 'Bangalore', pincode: '560037' },
  { label: 'Carmelaram, Bangalore',          parent: 'Sarjapur Road',      city: 'Bangalore', pincode: '560035' },
  { label: 'Haralur Road, Bangalore',        parent: 'HSR Layout',         city: 'Bangalore', pincode: '560102' },
  { label: 'Iblur, Bangalore',               parent: 'HSR Layout',         city: 'Bangalore', pincode: '560102' },
  { label: 'Sarjapur, Bangalore',            parent: 'Sarjapur Road',      city: 'Bangalore', pincode: '562125' },
  { label: 'Outer Ring Road Bellandur, Bangalore', parent: 'Bellandur',    city: 'Bangalore', pincode: '560103' },
  // ── Bangalore — North ───────────────────────────────────────
  { label: 'Manyata Tech Park, Bangalore',   parent: 'Hebbal',             city: 'Bangalore', pincode: '560045' },
  { label: 'Thanisandra, Bangalore',         parent: 'Hebbal',             city: 'Bangalore', pincode: '560077' },
  { label: 'Nagawara, Bangalore',            parent: 'Hennur',             city: 'Bangalore', pincode: '560045' },
  { label: 'Kalyan Nagar, Bangalore',        parent: 'Banaswadi',          city: 'Bangalore', pincode: '560043' },
  { label: 'HRBR Layout, Bangalore',         parent: 'Banaswadi',          city: 'Bangalore', pincode: '560043' },
  { label: 'HBR Layout, Bangalore',          parent: 'Hennur',             city: 'Bangalore', pincode: '560043' },
  { label: 'Yelahanka New Town, Bangalore',  parent: 'Yelahanka',          city: 'Bangalore', pincode: '560064' },
  { label: 'Jakkur, Bangalore',              parent: 'Yelahanka',          city: 'Bangalore', pincode: '560064' },
  // ── Bangalore — South periphery ─────────────────────────────
  { label: 'Hosur Road, Bangalore',          parent: 'Electronic City',    city: 'Bangalore', pincode: '560100' },
  { label: 'Bommasandra, Bangalore',         parent: 'Electronic City',    city: 'Bangalore', pincode: '560099' },
];

/* Combined list used for autocomplete searches. Aliases are flagged so the
 * picker handler knows to substitute the parent for price lookup. */
function getCombinedLocalities() {
  const main = LOCALITIES.map(l => ({ ...l, isAlias: false }));
  const aliases = LOCALITY_ALIASES.map(a => ({
    label: a.label, city: a.city, pincode: a.pincode,
    parent: a.parent, isAlias: true
  }));
  return main.concat(aliases);
}

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

  const all = getCombinedLocalities();
  const matches = all.filter(l =>
    l.label.toLowerCase().includes(query)
  ).slice(0, 10);

  if (matches.length === 0) { suggestBox.style.display = 'none'; return; }

  suggestBox.style.display = 'block';
  matches.forEach(loc => {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    div.textContent = loc.label;
    div.onclick = () => {
      input.value = loc.label;
      document.getElementById('f-pincode').value = loc.pincode;
      // For aliases, store the parent name as the "locality" so PRICE_DB
      // lookup uses the parent's rates. The user still sees the alias label.
      selectedLocality = loc.isAlias
        ? { label: `${loc.parent}, ${loc.city}`, city: loc.city, pincode: loc.pincode, aliasLabel: loc.label }
        : loc;
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
