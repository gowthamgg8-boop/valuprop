/**
 * ValUprop.in — Results Page JS (Phase 2 + Aggressive Preview)
 * Polls backend for LLM estimate. Falls back to static data if offline.
 * Renders an aggressive A–F preview using PRICE_DB to drive ₹99 conversion.
 */

const BACKEND_URL = window.BACKEND_URL || 'https://valuprop-api.onrender.com';
let _poll = 0;

/* ─── PRICE_DB ───────────────────────────────────────────────────
 * apt:    [Lo, Hi] in lakhs for a typical 2 BHK in this locality
 * house:  [Lo, Hi] in lakhs for a typical built-up independent house
 * villa:  [Lo, Hi] in lakhs for a typical villa in gated community
 * land:   [Lo, Hi] in lakhs for a typical residential plot
 * trend:  12-month YoY apparent price movement
 * sqft:   benchmark land rate in ₹/sqft for the locality
 * pincode: primary pincode for this locality (drives the pincode fallback)
 *
 * NEW LOCALITIES (May/Jun 2026): rates are best-guess estimates anchored to
 * neighbouring localities + tier classification. Recommend Prabhakar
 * spot-checks against real Chennai/Bangalore transactions and adjusts.
 *
 * IMPORTANT: ALL RATES BELOW ARE INHERITED FROM EARLIER CODEBASE OR
 * BEST-GUESS ESTIMATES. A FULL RATE AUDIT IS PENDING IN A SEPARATE SESSION.
 */
const PRICE_DB = {
  Chennai: {
    // ── Central / Premium ───────────────────────────────────
    'Anna Nagar':       {apt:[48,74],  house:[220,340], villa:[380,560], land:[95,140],  trend:'+6.2%', sqft:4850, pincode:'600040'},
    'Anna Nagar West':  {apt:[38,58],  house:[160,240], villa:[270,405], land:[70,105],  trend:'+8.0%', sqft:4100, pincode:'600101'},
    'T. Nagar':         {apt:[55,88],  house:[280,420], villa:[450,680], land:[110,165], trend:'+7.5%', sqft:5200, pincode:'600017'},
    'Nungambakkam':     {apt:[65,105], house:[380,570], villa:[600,900], land:[140,210], trend:'+4.5%', sqft:5800, pincode:'600034'},
    'Kilpauk':          {apt:[50,80],  house:[245,368], villa:[420,630], land:[105,158], trend:'+6.0%', sqft:4800, pincode:'600010'},
    'Shenoy Nagar':     {apt:[60,95],  house:[420,520], villa:[580,800], land:[130,200], trend:'+5.5%', sqft:5600, pincode:'600030'},
    'Egmore':           {apt:[55,85],  house:[300,450], villa:[480,720], land:[115,170], trend:'+5.0%', sqft:5100, pincode:'600008'},
    'Triplicane':       {apt:[42,65],  house:[200,300], villa:[330,495], land:[80,120],  trend:'+5.2%', sqft:3800, pincode:'600005'},
    'Royapettah':       {apt:[48,75],  house:[240,360], villa:[400,600], land:[100,150], trend:'+5.5%', sqft:4500, pincode:'600014'},
    'Alwarpet':         {apt:[80,128], house:[460,680], villa:[720,1080],land:[170,255], trend:'+4.5%', sqft:6800, pincode:'600018'},
    'Mylapore':         {apt:[55,85],  house:[290,440], villa:[480,720], land:[115,175], trend:'+5.0%', sqft:5100, pincode:'600004'},
    'Teynampet':        {apt:[75,118], house:[420,630], villa:[660,990], land:[155,235], trend:'+4.8%', sqft:6200, pincode:'600086'},
    'R.A. Puram':       {apt:[78,122], house:[440,660], villa:[700,1050],land:[165,245], trend:'+5.0%', sqft:6500, pincode:'600028'},
    'Boat Club Road':   {apt:[120,200],house:[700,1100],villa:[1200,1800],land:[280,420],trend:'+3.5%', sqft:11000,pincode:'600028'},
    'Mandaveli':        {apt:[58,90],  house:[300,450], villa:[500,750], land:[120,180], trend:'+5.2%', sqft:5300, pincode:'600028'},
    'Aminjikarai':      {apt:[42,68],  house:[200,300], villa:[345,520], land:[85,128],  trend:'+6.5%', sqft:4400, pincode:'600029'},
    // ── South / Coastal ─────────────────────────────────────
    'Adyar':            {apt:[60,95],  house:[310,470], villa:[520,780], land:[120,180], trend:'+4.8%', sqft:5400, pincode:'600020'},
    'Kotturpuram':      {apt:[70,108], house:[360,540], villa:[600,900], land:[140,210], trend:'+5.0%', sqft:5900, pincode:'600085'},
    'Saidapet':         {apt:[42,66],  house:[195,290], villa:[330,495], land:[80,120],  trend:'+5.5%', sqft:4000, pincode:'600015'},
    'Thiruvanmiyur':    {apt:[55,88],  house:[280,420], villa:[470,705], land:[110,165], trend:'+5.8%', sqft:5000, pincode:'600041'},
    'Besant Nagar':     {apt:[68,105], house:[350,525], villa:[580,870], land:[135,205], trend:'+5.2%', sqft:5700, pincode:'600090'},
    'Velachery':        {apt:[38,60],  house:[160,240], villa:[280,420], land:[70,105],  trend:'+8.8%', sqft:4100, pincode:'600042'},
    'Ekkattuthangal':   {apt:[40,64],  house:[170,255], villa:[295,440], land:[75,113],  trend:'+7.5%', sqft:4200, pincode:'600032'},
    'Nanganallur':      {apt:[36,58],  house:[155,232], villa:[270,405], land:[68,102],  trend:'+8.0%', sqft:3900, pincode:'600061'},
    // ── IT Corridor / OMR ───────────────────────────────────
    'Perungudi':        {apt:[42,66],  house:[180,270], villa:[300,450], land:[78,117],  trend:'+9.4%', sqft:4300, pincode:'600096'},
    'Thoraipakkam':     {apt:[44,70],  house:[185,278], villa:[315,470], land:[80,120],  trend:'+9.8%', sqft:4400, pincode:'600097'},
    'Karapakkam':       {apt:[40,62],  house:[170,255], villa:[290,435], land:[72,108],  trend:'+10.5%',sqft:4000, pincode:'600097'},
    'Sholinganallur':   {apt:[44,68],  house:[185,278], villa:[310,465], land:[80,120],  trend:'+9.4%', sqft:4400, pincode:'600119'},
    'Navalur':          {apt:[34,55],  house:[140,210], villa:[245,365], land:[58,87],   trend:'+11.5%',sqft:3500, pincode:'600130'},
    'Siruseri':         {apt:[36,57],  house:[145,218], villa:[255,380], land:[62,93],   trend:'+11.8%',sqft:3700, pincode:'603103'},
    'Kelambakkam':      {apt:[28,46],  house:[110,165], villa:[195,290], land:[48,72],   trend:'+13.0%',sqft:3000, pincode:'603103'},
    'Pallikaranai':     {apt:[35,56],  house:[150,225], villa:[260,390], land:[64,96],   trend:'+11.0%',sqft:3700, pincode:'600100'},
    'Medavakkam':       {apt:[32,52],  house:[135,200], villa:[235,350], land:[58,87],   trend:'+11.5%',sqft:3400, pincode:'600100'},
    // ── West / Porur belt ───────────────────────────────────
    'Porur':            {apt:[32,52],  house:[120,180], villa:[200,300], land:[55,82],   trend:'+10.2%',sqft:3700, pincode:'600116'},
    'Manapakkam':       {apt:[30,48],  house:[115,170], villa:[195,290], land:[52,78],   trend:'+10.8%',sqft:3500, pincode:'600125'},
    'Iyyappanthangal':  {apt:[28,45],  house:[105,158], villa:[180,270], land:[48,72],   trend:'+11.5%',sqft:3300, pincode:'600056'},
    'Vadapalani':       {apt:[45,70],  house:[210,315], villa:[360,540], land:[88,132],  trend:'+6.5%', sqft:4500, pincode:'600026'},
    'K.K. Nagar':       {apt:[48,75],  house:[235,350], villa:[400,600], land:[98,147],  trend:'+6.2%', sqft:4700, pincode:'600078'},
    'Ashok Nagar':      {apt:[46,72],  house:[225,335], villa:[380,570], land:[94,141],  trend:'+6.5%', sqft:4600, pincode:'600083'},
    'Mogappair':        {apt:[35,58],  house:[155,232], villa:[270,405], land:[65,98],   trend:'+9.1%', sqft:4200, pincode:'600037'},
    'Valasaravakkam':   {apt:[36,58],  house:[155,232], villa:[270,405], land:[68,102],  trend:'+9.0%', sqft:4100, pincode:'600087'},
    'Saligramam':       {apt:[40,62],  house:[175,262], villa:[300,450], land:[78,117],  trend:'+8.0%', sqft:4300, pincode:'600093'},
    'Choolaimedu':      {apt:[44,68],  house:[200,300], villa:[345,518], land:[85,128],  trend:'+7.0%', sqft:4400, pincode:'600094'},
    'Virugambakkam':    {apt:[34,55],  house:[150,225], villa:[260,390], land:[64,96],   trend:'+9.0%', sqft:3900, pincode:'600092'},
    // ── North / Outer ───────────────────────────────────────
    'Perambur':         {apt:[26,44],  house:[100,150], villa:[180,270], land:[45,68],   trend:'+11.8%',sqft:3200, pincode:'600011'},
    'Padi':             {apt:[28,45],  house:[110,165], villa:[190,285], land:[50,75],   trend:'+10.8%',sqft:3400, pincode:'600050'},
    'Korattur':         {apt:[26,42],  house:[100,150], villa:[180,270], land:[46,69],   trend:'+11.5%',sqft:3200, pincode:'600076'},
    'Ambattur':         {apt:[24,40],  house:[92,138],  villa:[165,250], land:[42,63],   trend:'+12.0%',sqft:3000, pincode:'600053'},
    'Avadi':            {apt:[20,34],  house:[78,118],  villa:[140,210], land:[36,54],   trend:'+13.5%',sqft:2600, pincode:'600054'},
    // ── South Periphery / GST Road ──────────────────────────
    'Chromepet':        {apt:[28,46],  house:[105,158], villa:[185,280], land:[48,72],   trend:'+11.3%',sqft:3400, pincode:'600044'},
    'Pallavaram':       {apt:[27,45],  house:[102,153], villa:[180,270], land:[46,70],   trend:'+10.8%',sqft:3300, pincode:'600043'},
    'Tambaram':         {apt:[24,40],  house:[90,135],  villa:[160,240], land:[40,60],   trend:'+12.6%',sqft:3100, pincode:'600045'},
    'Selaiyur':         {apt:[25,42],  house:[95,142],  villa:[170,255], land:[42,63],   trend:'+12.0%',sqft:3200, pincode:'600073'},
    'Madambakkam':      {apt:[23,38],  house:[88,132],  villa:[158,235], land:[40,60],   trend:'+12.5%',sqft:3000, pincode:'600126'},
    'Urapakkam':        {apt:[20,34],  house:[78,118],  villa:[140,210], land:[36,54],   trend:'+13.5%',sqft:2700, pincode:'603210'},
    'Vandalur':         {apt:[21,35],  house:[80,120],  villa:[145,218], land:[37,55],   trend:'+13.2%',sqft:2800, pincode:'600048'},
    'Mudichur':         {apt:[20,34],  house:[78,118],  villa:[140,210], land:[36,54],   trend:'+13.5%',sqft:2700, pincode:'600048'},
    'Guduvanchery':     {apt:[19,32],  house:[74,110],  villa:[135,200], land:[34,51],   trend:'+14.0%',sqft:2600, pincode:'603202'},
    'Maraimalai Nagar': {apt:[18,30],  house:[70,105],  villa:[125,190], land:[32,48],   trend:'+14.5%',sqft:2400, pincode:'603209'},
  },
  Bangalore: {
    // ── Central / Premium ───────────────────────────────────
    'Indiranagar':      {apt:[75,118], house:[420,630], villa:[720,1080],land:[175,265], trend:'+8.4%', sqft:6300, pincode:'560038'},
    'Koramangala':      {apt:[70,110], house:[380,570], villa:[650,975], land:[160,240], trend:'+9.8%', sqft:6100, pincode:'560034'},
    'Jayanagar':        {apt:[65,102], house:[320,480], villa:[560,840], land:[140,210], trend:'+7.4%', sqft:5700, pincode:'560041'},
    'Sadashivanagar':   {apt:[110,170],house:[620,930], villa:[1050,1575],land:[250,375],trend:'+5.5%', sqft:9500, pincode:'560080'},
    'Malleshwaram':     {apt:[68,108], house:[380,570], villa:[640,960], land:[155,235], trend:'+6.8%', sqft:5900, pincode:'560003'},
    'Rajajinagar':      {apt:[55,86],  house:[300,450], villa:[510,765], land:[125,188], trend:'+7.2%', sqft:4900, pincode:'560010'},
    'Frazer Town':      {apt:[75,118], house:[410,615], villa:[700,1050],land:[170,255], trend:'+6.5%', sqft:6400, pincode:'560005'},
    'Cooke Town':       {apt:[78,122], house:[430,645], villa:[730,1095],land:[175,265], trend:'+6.5%', sqft:6600, pincode:'560005'},
    'Richmond Town':    {apt:[95,150], house:[540,810], villa:[920,1380],land:[220,330], trend:'+5.5%', sqft:8400, pincode:'560025'},
    'Lavelle Road':     {apt:[110,170],house:[620,930], villa:[1050,1575],land:[250,375],trend:'+5.0%', sqft:9800, pincode:'560001'},
    'Basavanagudi':     {apt:[65,102], house:[355,535], villa:[600,900], land:[145,220], trend:'+6.8%', sqft:5500, pincode:'560004'},
    // ── South ───────────────────────────────────────────────
    'JP Nagar':         {apt:[58,92],  house:[290,435], villa:[500,750], land:[125,188], trend:'+7.8%', sqft:5100, pincode:'560078'},
    'BTM Layout':       {apt:[48,78],  house:[210,315], villa:[370,555], land:[100,150], trend:'+12.1%',sqft:4900, pincode:'560076'},
    'HSR Layout':       {apt:[60,96],  house:[280,420], villa:[490,735], land:[130,195], trend:'+10.9%',sqft:5500, pincode:'560102'},
    'Bannerghatta Road':{apt:[44,72],  house:[200,300], villa:[350,525], land:[92,138],  trend:'+11.5%',sqft:4500, pincode:'560076'},
    'Bommanahalli':     {apt:[40,65],  house:[180,270], villa:[310,465], land:[82,123],  trend:'+12.0%',sqft:4200, pincode:'560068'},
    'Begur':            {apt:[36,58],  house:[160,240], villa:[280,420], land:[74,111],  trend:'+12.8%',sqft:3800, pincode:'560068'},
    'Hulimavu':         {apt:[38,62],  house:[170,255], villa:[300,450], land:[78,117],  trend:'+12.0%',sqft:4000, pincode:'560076'},
    'Banashankari':     {apt:[50,80],  house:[235,353], villa:[410,615], land:[105,158], trend:'+9.0%', sqft:4700, pincode:'560070'},
    'Vijayanagar':      {apt:[46,74],  house:[215,323], villa:[375,565], land:[96,144],  trend:'+8.5%', sqft:4400, pincode:'560040'},
    // ── East / IT Belt ──────────────────────────────────────
    'Whitefield':       {apt:[52,85],  house:[240,360], villa:[420,630], land:[110,165], trend:'+12.2%',sqft:5200, pincode:'560066'},
    'Marathahalli':     {apt:[45,72],  house:[200,300], villa:[350,525], land:[95,143],  trend:'+13.5%',sqft:4700, pincode:'560037'},
    'Sarjapur Road':    {apt:[52,84],  house:[240,360], villa:[420,630], land:[112,168], trend:'+12.5%',sqft:5300, pincode:'560035'},
    'Bellandur':        {apt:[55,88],  house:[255,383], villa:[440,660], land:[118,177], trend:'+12.0%',sqft:5500, pincode:'560103'},
    'Doddanekundi':     {apt:[48,76],  house:[215,323], villa:[375,565], land:[100,150], trend:'+13.0%',sqft:4900, pincode:'560037'},
    'Mahadevapura':     {apt:[50,80],  house:[225,338], villa:[395,593], land:[105,158], trend:'+12.5%',sqft:5100, pincode:'560048'},
    'ITPL Main Road':   {apt:[54,86],  house:[245,368], villa:[425,638], land:[115,173], trend:'+12.0%',sqft:5400, pincode:'560066'},
    'KR Puram':         {apt:[42,68],  house:[190,285], villa:[330,495], land:[88,132],  trend:'+13.5%',sqft:4400, pincode:'560036'},
    // ── North ───────────────────────────────────────────────
    'Hebbal':           {apt:[56,90],  house:[260,390], villa:[460,690], land:[120,180], trend:'+11.3%',sqft:5300, pincode:'560024'},
    'Yelahanka':        {apt:[38,62],  house:[170,255], villa:[300,450], land:[82,123],  trend:'+14.2%',sqft:4300, pincode:'560064'},
    'Devanahalli':      {apt:[32,52],  house:[140,210], villa:[245,365], land:[68,102],  trend:'+15.5%',sqft:3500, pincode:'562110'},
    'Hennur':           {apt:[42,68],  house:[195,290], villa:[340,510], land:[90,135],  trend:'+13.2%',sqft:4500, pincode:'560043'},
    'Banaswadi':        {apt:[44,70],  house:[205,308], villa:[358,538], land:[94,141],  trend:'+12.5%',sqft:4600, pincode:'560043'},
    // ── South Periphery ────────────────────────────────────
    'Electronic City':  {apt:[35,58],  house:[160,240], villa:[280,420], land:[75,113],  trend:'+15.0%',sqft:4200, pincode:'560100'},
  }
};

/* Locality tier classification — drives section B narrative.
 * Each new locality has been classified based on its character. */
const LOCALITY_TIER = {
  // Chennai — premium / mature
  'Alwarpet':'premium', 'Adyar':'premium', 'Nungambakkam':'premium', 'Mylapore':'premium',
  'Shenoy Nagar':'premium', 'T. Nagar':'premium', 'Kilpauk':'premium', 'Teynampet':'premium',
  'R.A. Puram':'premium', 'Boat Club Road':'premium', 'Kotturpuram':'premium',
  'Besant Nagar':'premium', 'Egmore':'premium', 'Royapettah':'premium', 'Mandaveli':'premium',
  // Chennai — established
  'Anna Nagar':'established', 'Anna Nagar West':'established', 'Velachery':'established',
  'Mogappair':'established', 'Vadapalani':'established', 'K.K. Nagar':'established',
  'Ashok Nagar':'established', 'Triplicane':'established', 'Saidapet':'established',
  'Thiruvanmiyur':'established', 'Aminjikarai':'established', 'Choolaimedu':'established',
  'Saligramam':'established',
  // Chennai — emerging
  'Porur':'emerging', 'Sholinganallur':'emerging', 'Thoraipakkam':'emerging',
  'Perungudi':'emerging', 'Pallikaranai':'emerging', 'Manapakkam':'emerging',
  'Medavakkam':'emerging', 'Valasaravakkam':'emerging', 'Virugambakkam':'emerging',
  'Ekkattuthangal':'emerging', 'Nanganallur':'emerging',
  // Chennai — peripheral / high-growth
  'Perambur':'peripheral', 'Chromepet':'peripheral', 'Tambaram':'peripheral',
  'Pallavaram':'peripheral', 'Padi':'peripheral', 'Korattur':'peripheral',
  'Ambattur':'peripheral', 'Avadi':'peripheral', 'Karapakkam':'peripheral',
  'Navalur':'peripheral', 'Siruseri':'peripheral', 'Kelambakkam':'peripheral',
  'Iyyappanthangal':'peripheral', 'Selaiyur':'peripheral', 'Madambakkam':'peripheral',
  'Urapakkam':'peripheral', 'Vandalur':'peripheral', 'Mudichur':'peripheral',
  'Guduvanchery':'peripheral', 'Maraimalai Nagar':'peripheral',

  // Bangalore — premium / mature
  'Indiranagar':'premium', 'Koramangala':'premium', 'Jayanagar':'premium',
  'Sadashivanagar':'premium', 'Malleshwaram':'premium', 'Frazer Town':'premium',
  'Cooke Town':'premium', 'Richmond Town':'premium', 'Lavelle Road':'premium',
  'Basavanagudi':'premium',
  // Bangalore — established
  'HSR Layout':'established', 'Hebbal':'established', 'BTM Layout':'established',
  'JP Nagar':'established', 'Rajajinagar':'established', 'Banashankari':'established',
  'Vijayanagar':'established',
  // Bangalore — emerging
  'Whitefield':'emerging', 'Marathahalli':'emerging', 'Sarjapur Road':'emerging',
  'Bellandur':'emerging', 'Mahadevapura':'emerging', 'ITPL Main Road':'emerging',
  'Doddanekundi':'emerging', 'Bommanahalli':'emerging',
  // Bangalore — peripheral / high-growth
  'Electronic City':'peripheral', 'Yelahanka':'peripheral', 'Devanahalli':'peripheral',
  'Hennur':'peripheral', 'Banaswadi':'peripheral', 'KR Puram':'peripheral',
  'Begur':'peripheral', 'Hulimavu':'peripheral', 'Bannerghatta Road':'peripheral',
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

/* ─── Locality lookup — 3-step matching logic ──────────────────
 * Step 1: Exact name match in PRICE_DB
 * Step 2: Pincode lookup (find any PRICE_DB entry with same pincode)
 * Step 3: City-wide average (clearly labelled)
 *
 * Returns: { db, matched, source }
 *   db:      the rate data object
 *   matched: the locality name we ended up using
 *   source:  'exact' | 'pincode' | 'city_avg'
 */
function lookupLocality(city, locality, pincode) {
  const cityDb = PRICE_DB[city];
  if (!cityDb) {
    // Unknown city — default to Chennai city average
    return cityAverageLookup('Chennai');
  }

  // ── Step 1: Exact name match (case-insensitive, trimmed) ──
  if (locality) {
    const needle = locality.toLowerCase().trim();
    for (const key of Object.keys(cityDb)) {
      if (key.toLowerCase() === needle) {
        return { db: cityDb[key], matched: key, source: 'exact' };
      }
    }
  }

  // ── Step 2: Pincode match ──
  if (pincode) {
    const pinClean = String(pincode).trim();
    for (const key of Object.keys(cityDb)) {
      if (cityDb[key].pincode === pinClean) {
        return { db: cityDb[key], matched: key, source: 'pincode' };
      }
    }
  }

  // ── Step 3: City-wide average ──
  return cityAverageLookup(city);
}

/* Compute city-wide averages from all PRICE_DB entries in the city. */
function cityAverageLookup(city) {
  const cityDb = PRICE_DB[city] || PRICE_DB.Chennai;
  const entries = Object.values(cityDb);
  const avg = (key) => {
    const sum = entries.reduce((s, e) => s + ((e[key]?.[0] || 0) + (e[key]?.[1] || 0)) / 2, 0);
    return Math.round(sum / entries.length);
  };
  const avgArr = (key) => {
    const lo = Math.round(entries.reduce((s, e) => s + (e[key]?.[0] || 0), 0) / entries.length);
    const hi = Math.round(entries.reduce((s, e) => s + (e[key]?.[1] || 0), 0) / entries.length);
    return [lo, hi];
  };
  const avgSqft = Math.round(entries.reduce((s, e) => s + (e.sqft || 0), 0) / entries.length);

  return {
    db: {
      apt:   avgArr('apt'),
      house: avgArr('house'),
      villa: avgArr('villa'),
      land:  avgArr('land'),
      sqft:  avgSqft,
      trend: '+8.5%', // generic city-level number
      pincode: ''
    },
    matched: `${city} (city average)`,
    source: 'city_avg'
  };
}

function renderStatic(search) {
  const city = search.city || 'Chennai';
  const loc  = search.locality || '';
  const pin  = search.pincode || '';
  const hit  = lookupLocality(city, loc, pin);
  const db   = hit.db;

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
   ============================================================ */
function renderPreview(search) {
  const city = search.city || 'Chennai';
  const loc  = search.locality || '';
  const pin  = search.pincode || '';
  const hit  = lookupLocality(city, loc, pin);
  const db   = hit.db;
  const matchedLoc = hit.matched;
  const source = hit.source;
  // Tier lookup — strip "(city average)" suffix if present
  const tierKey = matchedLoc.includes('(') ? null : matchedLoc;
  const tier = LOCALITY_TIER[tierKey] || 'established';

  renderSectionA(search, db, source, matchedLoc);
  renderSectionB(search, db, tier, matchedLoc, city, source);
  renderSectionC(search, db, matchedLoc, source);
  renderSectionD(search, db);
  renderSectionF(search);
}

function renderSectionA(s, db, source, matchedLoc) {
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

function renderSectionB(s, db, tier, loc, city, source) {
  const trend = db.trend;
  const sqftRate = db.sqft.toLocaleString('en-IN');

  // Match-source note — small honest banner above the narrative
  let sourceNote = '';
  if (source === 'pincode') {
    sourceNote = `<p style="background:#f0f9ff; border-left:3px solid #0284c7; padding:8px 12px; font-size:12px; color:#075985; margin-bottom:10px;">
      <strong>Note:</strong> Rate based on nearest mapped area (${escapeHtml(loc)}) using your pincode. Your paid report uses property-specific signals.</p>`;
  } else if (source === 'city_avg') {
    sourceNote = `<p style="background:#fef3c7; border-left:3px solid #d97706; padding:8px 12px; font-size:12px; color:#78350f; margin-bottom:10px;">
      <strong>Note:</strong> We do not yet have specific data for this exact area. Showing ${escapeHtml(city)} city-wide average. Your detailed ₹99 report uses property-specific signals and live market data.</p>`;
  }

  let para1;
  if (source === 'city_avg') {
    para1 = `${city} as a whole has a wide spread of micro-markets — from premium central pockets to high-growth periphery. The numbers below reflect a citywide blended view; your detailed report will pull location-specific signals.`;
  } else {
    const tierNarrative = {
      premium: `${loc} is one of ${city}\u2019s most established premium pockets, characterised by mature infrastructure, established schools and hospitals, and a stable resident profile. Inventory turnover here is typically lower, with sellers commanding pricing power.`,
      established: `${loc} is a well-established residential micro-market in ${city} with mature infrastructure, strong rental demand, and a healthy mix of older standalone buildings and newer gated developments. Demand here is broad-based across families and working professionals.`,
      emerging: `${loc} is an actively emerging micro-market in ${city} \u2014 driven by IT/ITES employment hubs, ongoing infrastructure upgrades, and new gated developments coming online. This tier typically shows above-average price appreciation but also higher inventory churn.`,
      peripheral: `${loc} is a high-growth peripheral micro-market in ${city}, benefiting from metro/road connectivity expansion, new affordable-to-mid-segment supply, and outward demand spillover from inner suburbs. Appreciation potential here is among the highest in the city, paired with longer absorption timelines.`
    };
    para1 = tierNarrative[tier] || tierNarrative.established;
  }

  const para2 = `Locality benchmark land rate is approximately <strong>\u20b9${sqftRate}/sq.ft</strong>. Over the past 12 months, properties in this micro-market have moved <strong>${trend}</strong>, ${parseFloat(trend) > 8 ? 'meaningfully outperforming' : parseFloat(trend) > 5 ? 'tracking close to' : 'underperforming'} the broader ${city} residential index.`;

  document.getElementById('rep-b-body').innerHTML =
    `${sourceNote}<p>${para1}</p><p>${para2}</p>`;
}

function renderSectionC(s, db, loc, source) {
  const sqftRate = db.sqft;
  const rows = [];

  rows.push({
    label: 'Locality land rate',
    value: `\u20b9${sqftRate.toLocaleString('en-IN')}/sq.ft`,
    meta: source === 'city_avg' ? 'City-wide average — your paid report uses property-specific data'
        : source === 'pincode'  ? `Mapped via pincode to nearest area (${loc})`
        : 'Benchmark for sale transactions in this micro-market'
  });

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

  rows.push({
    label: '12-month price trend',
    value: db.trend,
    meta: 'Year-on-year appreciation in this locality'
  });

  rows.push({
    label: 'Indicative guideline value',
    value: `<span class="rep-blur">\u20b9XX,XXX/sq.ft</span>`,
    meta: 'State-published rate \u2014 in your ₹99 report'
  });

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

function renderSectionD(s, db) {
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
