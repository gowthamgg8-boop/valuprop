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
/* PRICE_DB v2 — rebuilt from chennai_cma_locality_seed.csv (Jun 2026)
 * 165 CMA + GCC localities sourced from seed CSV, plus 8 premium central
 * localities preserved from prior PRICE_DB. Rates are best-available for the
 * confidence flag shown; 'low' confidence entries need spot-checks before launch.
 *
 * Each entry includes:
 *   sqft        — locality benchmark flat rate (₹/sqft super-built-up)
 *   apt/house/villa/land — lakh-band ranges derived from sqft × multipliers
 *   trend       — 12-month YoY (tier-based)
 *   pincode     — primary pincode (drives pincode-fallback matching)
 *   confidence  — 'high' | 'medium' | 'low' (UI surfaces low-confidence)
 *   tier        — 'premium' | 'established' | 'emerging' | 'peripheral'
 *   gccZone     — CGCC zone or CMA boundary classification
 */

const PRICE_DB = {
  Chennai: {
    // ── PREMIUM ──
    'Adyar': {apt:[175,229],house:[821,1155],villa:[1368,1857],land:[342,502],trend:'+5.5%',sqft:15700,pincode:'600020',confidence:'high'},
    'Akkarai': {apt:[114,169],house:[602,996],villa:[1004,1602],land:[251,433],trend:'+5.5%',sqft:10900,pincode:'600119',confidence:'low'},
    'Alwarpet': {apt:[217,314],house:[1094,1835],villa:[1824,2953],land:[456,798],trend:'+5.5%',sqft:19950,pincode:'600018',confidence:'high'},
    'Aminjikarai': {apt:[103,151],house:[492,734],villa:[820,1180],land:[205,319],trend:'+6.5%',sqft:9500,pincode:'600029',confidence:'medium'},
    'Anna Nagar': {apt:[145,217],house:[710,1102],villa:[1184,1772],land:[296,479],trend:'+6.5%',sqft:13300,pincode:'600040',confidence:'high'},
    'Anna Nagar West': {apt:[121,175],house:[602,892],villa:[1004,1436],land:[251,388],trend:'+6.5%',sqft:11400,pincode:'600101',confidence:'medium'},
    'Ashok Nagar': {apt:[121,175],house:[602,892],villa:[1004,1436],land:[251,388],trend:'+6.0%',sqft:11400,pincode:'600083',confidence:'medium'},
    'Besant Nagar': {apt:[169,224],house:[876,1205],villa:[1460,1939],land:[365,524],trend:'+5.5%',sqft:15200,pincode:'600090',confidence:'high'},
    'Chetpet': {apt:[145,211],house:[710,1049],villa:[1184,1687],land:[296,456],trend:'+5.5%',sqft:13800,pincode:'600031',confidence:'medium'},
    'Choolaimedu': {apt:[97,138],house:[466,706],villa:[776,1136],land:[194,307],trend:'+6.0%',sqft:9000,pincode:'600094',confidence:'low'},
    'Egmore': {apt:[133,199],house:[658,996],villa:[1096,1602],land:[274,433],trend:'+5.5%',sqft:12800,pincode:'600008',confidence:'medium'},
    'Gopalapuram': {apt:[193,290],house:[984,1573],villa:[1640,2531],land:[410,684],trend:'+5.5%',sqft:18050,pincode:'600086',confidence:'medium'},
    'Guindy': {apt:[109,163],house:[492,734],villa:[820,1180],land:[205,319],trend:'+5.5%',sqft:10450,pincode:'600032',confidence:'medium'},
    'Injambakkam': {apt:[114,169],house:[547,943],villa:[912,1517],land:[228,410],trend:'+5.5%',sqft:10900,pincode:'600115',confidence:'medium'},
    'KK Nagar': {apt:[109,163],house:[547,839],villa:[912,1350],land:[228,365],trend:'+6.0%',sqft:10450,pincode:'600078',confidence:'medium'},
    'Kodambakkam': {apt:[109,163],house:[547,839],villa:[912,1350],land:[228,365],trend:'+6.0%',sqft:10450,pincode:'600024',confidence:'medium'},
    'Kolathur': {apt:[66,97],house:[274,409],villa:[456,659],land:[114,178],trend:'+6.5%',sqft:6200,pincode:'600099',confidence:'high'},
    'Kottivakkam': {apt:[133,187],house:[658,996],villa:[1096,1602],land:[274,433],trend:'+5.5%',sqft:12350,pincode:'600041',confidence:'medium'},
    'Kotturpuram': {apt:[145,211],house:[710,1049],villa:[1184,1687],land:[296,456],trend:'+5.5%',sqft:13800,pincode:'600085',confidence:'low'},
    'MGR Nagar': {apt:[90,133],house:[437,681],villa:[728,1095],land:[182,296],trend:'+6.0%',sqft:8550,pincode:'600078',confidence:'low'},
    'Neelankarai': {apt:[121,187],house:[658,1155],villa:[1096,1857],land:[274,502],trend:'+5.5%',sqft:11900,pincode:'600115',confidence:'high'},
    'Nesapakkam': {apt:[97,138],house:[466,706],villa:[776,1136],land:[194,307],trend:'+6.0%',sqft:9000,pincode:'600078',confidence:'low'},
    'Nungambakkam': {apt:[181,265],house:[984,1573],villa:[1640,2531],land:[410,684],trend:'+5.5%',sqft:17100,pincode:'600034',confidence:'high'},
    'Palavakkam': {apt:[133,193],house:[710,1049],villa:[1184,1687],land:[296,456],trend:'+5.5%',sqft:12350,pincode:'600041',confidence:'medium'},
    'Periyar Nagar': {apt:[79,121],house:[358,552],villa:[596,888],land:[149,240],trend:'+6.5%',sqft:7600,pincode:'600082',confidence:'low'},
    'Purasawalkam': {apt:[133,211],house:[658,996],villa:[1096,1602],land:[274,433],trend:'+6.5%',sqft:13300,pincode:'600084',confidence:'high'},
    'Royapettah': {apt:[133,193],house:[658,996],villa:[1096,1602],land:[274,433],trend:'+5.5%',sqft:12350,pincode:'600014',confidence:'low'},
    'Saidapet': {apt:[97,151],house:[492,734],villa:[820,1180],land:[205,319],trend:'+5.5%',sqft:9500,pincode:'600015',confidence:'medium'},
    'Saligramam': {apt:[103,157],house:[492,734],villa:[820,1180],land:[205,319],trend:'+6.0%',sqft:10000,pincode:'600093',confidence:'low'},
    'Shenoy Nagar': {apt:[121,175],house:[602,839],villa:[1004,1350],land:[251,365],trend:'+6.5%',sqft:11400,pincode:'600030',confidence:'medium'},
    'T Nagar': {apt:[193,253],house:[984,1467],villa:[1640,2361],land:[410,638],trend:'+5.5%',sqft:16150,pincode:'600017',confidence:'high'},
    'Teynampet': {apt:[181,277],house:[931,1467],villa:[1552,2361],land:[388,638],trend:'+5.5%',sqft:17100,pincode:'600018',confidence:'high'},
    'Thiruvanmiyur': {apt:[145,199],house:[658,943],villa:[1096,1517],land:[274,410],trend:'+5.5%',sqft:13300,pincode:'600041',confidence:'medium'},
    'Thousand Lights': {apt:[169,253],house:[876,1364],villa:[1460,2194],land:[365,593],trend:'+5.5%',sqft:16150,pincode:'600006',confidence:'low'},
    'Triplicane': {apt:[97,157],house:[466,761],villa:[776,1225],land:[194,331],trend:'+5.5%',sqft:9500,pincode:'600005',confidence:'medium'},
    'Uthandi': {apt:[97,151],house:[437,787],villa:[728,1265],land:[182,342],trend:'+5.5%',sqft:9500,pincode:'600119',confidence:'low'},
    'Vadapalani': {apt:[114,169],house:[547,839],villa:[912,1350],land:[228,365],trend:'+6.0%',sqft:10900,pincode:'600026',confidence:'medium'},
    'Velachery': {apt:[95,159],house:[437,630],villa:[728,1014],land:[182,274],trend:'+5.5%',sqft:9000,pincode:'600042',confidence:'high'},
    'Vepery': {apt:[121,193],house:[547,892],villa:[912,1436],land:[228,388],trend:'+6.5%',sqft:12350,pincode:'600007',confidence:'low'},
    'Villivakkam': {apt:[84,127],house:[437,681],villa:[728,1095],land:[182,296],trend:'+6.5%',sqft:8100,pincode:'600049',confidence:'medium'},
    // ── ESTABLISHED ──
    'Adambakkam': {apt:[90,133],house:[408,630],villa:[680,1014],land:[170,274],trend:'+7.0%',sqft:8550,pincode:'600088',confidence:'medium'},
    'Alandur': {apt:[109,163],house:[518,812],villa:[864,1306],land:[216,353],trend:'+7.0%',sqft:10450,pincode:'600016',confidence:'medium'},
    'Alwarthirunagar': {apt:[84,127],house:[384,577],villa:[640,929],land:[160,251],trend:'+7.0%',sqft:8100,pincode:'600087',confidence:'low'},
    'Ayanavaram': {apt:[84,127],house:[384,577],villa:[640,929],land:[160,251],trend:'+7.5%',sqft:8100,pincode:'600023',confidence:'medium'},
    'Choolai': {apt:[82,127],house:[358,552],villa:[596,888],land:[149,240],trend:'+7.5%',sqft:8100,pincode:'600112',confidence:'low'},
    'Ennore': {apt:[55,84],house:[218,343],villa:[364,551],land:[91,149],trend:'+8.5%',sqft:5200,pincode:'600057',confidence:'low'},
    'Erukkancherry': {apt:[58,90],house:[247,377],villa:[412,607],land:[103,164],trend:'+7.5%',sqft:5500,pincode:'600118',confidence:'low'},
    'Iyyappanthangal': {apt:[66,103],house:[274,419],villa:[456,673],land:[114,182],trend:'+7.0%',sqft:6450,pincode:'600056',confidence:'medium'},
    'Kaladipet': {apt:[70,106],house:[286,430],villa:[476,692],land:[119,187],trend:'+8.5%',sqft:6650,pincode:'600019',confidence:'low'},
    'Kathivakkam': {apt:[51,79],house:[206,327],villa:[344,525],land:[86,142],trend:'+8.5%',sqft:4950,pincode:'600060',confidence:'low'},
    'Korukkupet': {apt:[70,109],house:[300,460],villa:[500,740],land:[125,200],trend:'+8.0%',sqft:6850,pincode:'600021',confidence:'low'},
    'Kosapet': {apt:[79,121],house:[341,524],villa:[568,844],land:[142,228],trend:'+7.5%',sqft:7600,pincode:'600012',confidence:'low'},
    'Maduravoyal': {apt:[79,114],house:[329,497],villa:[548,799],land:[137,216],trend:'+7.0%',sqft:7400,pincode:'600095',confidence:'low'},
    'Mannady': {apt:[109,181],house:[492,812],villa:[820,1306],land:[205,353],trend:'+7.5%',sqft:10900,pincode:'600001',confidence:'low'},
    'Meenambakkam': {apt:[79,114],house:[358,524],villa:[596,844],land:[149,228],trend:'+7.0%',sqft:7400,pincode:'600027',confidence:'low'},
    'Nanganallur': {apt:[97,145],house:[437,681],villa:[728,1095],land:[182,296],trend:'+7.0%',sqft:9000,pincode:'600061',confidence:'medium'},
    'Old Washermanpet': {apt:[72,114],house:[317,483],villa:[528,777],land:[132,210],trend:'+8.0%',sqft:7250,pincode:'600021',confidence:'high'},
    'Otteri': {apt:[79,121],house:[358,552],villa:[596,888],land:[149,240],trend:'+7.5%',sqft:7600,pincode:'600012',confidence:'low'},
    'Parrys': {apt:[103,175],house:[466,787],villa:[776,1265],land:[194,342],trend:'+7.5%',sqft:10450,pincode:'600001',confidence:'low'},
    'Pazhavanthangal': {apt:[97,145],house:[437,681],villa:[728,1095],land:[182,296],trend:'+7.0%',sqft:9000,pincode:'600114',confidence:'low'},
    'Perambur': {apt:[79,121],house:[329,497],villa:[548,799],land:[137,216],trend:'+7.5%',sqft:7600,pincode:'600011',confidence:'medium'},
    'Porur': {apt:[90,133],house:[384,603],villa:[640,969],land:[160,262],trend:'+7.0%',sqft:8550,pincode:'600116',confidence:'high'},
    'Pulianthope': {apt:[66,103],house:[286,430],villa:[476,692],land:[119,187],trend:'+7.5%',sqft:6450,pincode:'600012',confidence:'low'},
    'Ramapuram': {apt:[84,127],house:[372,552],villa:[620,888],land:[155,240],trend:'+7.0%',sqft:8100,pincode:'600089',confidence:'medium'},
    'Royapuram': {apt:[121,199],house:[518,839],villa:[864,1350],land:[216,365],trend:'+7.5%',sqft:12350,pincode:'600013',confidence:'high'},
    'Sembium': {apt:[72,114],house:[317,483],villa:[528,777],land:[132,210],trend:'+7.5%',sqft:7100,pincode:'600011',confidence:'low'},
    'Sowcarpet': {apt:[114,199],house:[547,915],villa:[912,1473],land:[228,398],trend:'+7.5%',sqft:11900,pincode:'600079',confidence:'low'},
    'St Thomas Mount': {apt:[103,151],house:[466,706],villa:[776,1136],land:[194,307],trend:'+7.0%',sqft:9500,pincode:'600016',confidence:'low'},
    'Tiruvottiyur': {apt:[72,114],house:[300,471],villa:[500,758],land:[125,205],trend:'+8.5%',sqft:7100,pincode:'600019',confidence:'high'},
    'Tollgate': {apt:[72,111],house:[300,471],villa:[500,758],land:[125,205],trend:'+8.0%',sqft:7000,pincode:'600021',confidence:'low'},
    'Tondiarpet': {apt:[84,138],house:[358,577],villa:[596,929],land:[149,251],trend:'+8.0%',sqft:8750,pincode:'600081',confidence:'high'},
    'Valasaravakkam': {apt:[84,127],house:[384,577],villa:[640,929],land:[160,251],trend:'+7.0%',sqft:8100,pincode:'600087',confidence:'medium'},
    'Virugambakkam': {apt:[97,145],house:[466,706],villa:[776,1136],land:[194,307],trend:'+7.0%',sqft:9000,pincode:'600092',confidence:'medium'},
    'Vyasarpadi': {apt:[60,94],house:[247,391],villa:[412,629],land:[103,170],trend:'+8.0%',sqft:5900,pincode:'600039',confidence:'low'},
    'Washermanpet': {apt:[79,127],house:[329,524],villa:[548,844],land:[137,228],trend:'+7.5%',sqft:7800,pincode:'600021',confidence:'medium'},
    'Wimco Nagar': {apt:[58,87],house:[230,356],villa:[384,574],land:[96,155],trend:'+8.5%',sqft:5500,pincode:'600057',confidence:'low'},
    // ── EMERGING ──
    'Karapakkam': {apt:[114,157],house:[329,430],villa:[548,692],land:[137,187],trend:'+6.5%',sqft:10450,pincode:'600097',confidence:'medium'},
    'Keelkattalai': {apt:[70,97],house:[262,356],villa:[436,574],land:[109,155],trend:'+6.5%',sqft:6450,pincode:'600117',confidence:'low'},
    'Kovilambakkam': {apt:[66,94],house:[247,343],villa:[412,551],land:[103,149],trend:'+6.5%',sqft:6200,pincode:'600129',confidence:'low'},
    'Madipakkam': {apt:[72,106],house:[300,409],villa:[500,659],land:[125,178],trend:'+6.5%',sqft:6850,pincode:'600091',confidence:'medium'},
    'Medavakkam': {apt:[66,99],house:[247,356],villa:[412,574],land:[103,155],trend:'+6.5%',sqft:6450,pincode:'600100',confidence:'high'},
    'Navalur': {apt:[82,114],house:[329,446],villa:[548,718],land:[137,194],trend:'+7.5%',sqft:7400,pincode:'600130',confidence:'high'},
    'Pallikaranai': {apt:[79,114],house:[300,409],villa:[500,659],land:[125,178],trend:'+6.5%',sqft:7400,pincode:'600100',confidence:'medium'},
    'Perumbakkam': {apt:[79,111],house:[300,391],villa:[500,629],land:[125,170],trend:'+7.5%',sqft:7400,pincode:'600100',confidence:'high'},
    'Perungudi': {apt:[163,217],house:[358,446],villa:[596,718],land:[149,194],trend:'+6.5%',sqft:14700,pincode:'600096',confidence:'high'},
    'Semmancheri': {apt:[66,94],house:[218,304],villa:[364,488],land:[91,132],trend:'+7.5%',sqft:6200,pincode:'600119',confidence:'low'},
    'Sholinganallur': {apt:[103,151],house:[317,409],villa:[528,659],land:[132,178],trend:'+7.5%',sqft:9500,pincode:'600119',confidence:'high'},
    'Siruseri': {apt:[72,103],house:[230,315],villa:[384,507],land:[96,137],trend:'+7.5%',sqft:6650,pincode:'603103',confidence:'high'},
    'Sithalapakkam': {apt:[60,87],house:[218,304],villa:[364,488],land:[91,132],trend:'+7.5%',sqft:5700,pincode:'600126',confidence:'low'},
    'Taramani': {apt:[121,181],house:[384,524],villa:[640,844],land:[160,228],trend:'+6.5%',sqft:11900,pincode:'600113',confidence:'medium'},
    'Thoraipakkam': {apt:[133,187],house:[329,409],villa:[548,659],land:[137,178],trend:'+6.5%',sqft:12350,pincode:'600097',confidence:'high'},
    // ── PERIPHERAL ──
    'Ambattur': {apt:[60,90],house:[262,377],villa:[436,607],land:[109,164],trend:'+8.0%',sqft:5700,pincode:'600053',confidence:'high'},
    'Anakaputhur': {apt:[55,84],house:[230,356],villa:[384,574],land:[96,155],trend:'+8.0%',sqft:5200,pincode:'600070',confidence:'low'},
    'Anna Nagar West Extn': {apt:[103,157],house:[437,681],villa:[728,1095],land:[182,296],trend:'+8.0%',sqft:10000,pincode:'600101',confidence:'medium'},
    'Arakkonam': {apt:[27,46],house:[67,147],villa:[112,237],land:[28,64],trend:'+7.0%',sqft:2650,pincode:'631001',confidence:'low'},
    'Avadi': {apt:[48,75],house:[206,315],villa:[344,507],land:[86,137],trend:'+10.0%',sqft:4750,pincode:'600054',confidence:'high'},
    'Ayappakkam': {apt:[55,84],house:[230,356],villa:[384,574],land:[96,155],trend:'+8.0%',sqft:5200,pincode:'600077',confidence:'low'},
    'Chengalpattu Town': {apt:[36,63],house:[110,237],villa:[184,381],land:[46,103],trend:'+10.0%',sqft:3600,pincode:'603001',confidence:'medium'},
    'Chromepet': {apt:[72,109],house:[317,471],villa:[528,758],land:[132,205],trend:'+8.0%',sqft:6850,pincode:'600044',confidence:'high'},
    'East Tambaram': {apt:[58,87],house:[230,368],villa:[384,592],land:[96,160],trend:'+8.0%',sqft:5500,pincode:'600059',confidence:'low'},
    'Guduvanchery': {apt:[46,70],house:[175,274],villa:[292,440],land:[73,119],trend:'+10.0%',sqft:4300,pincode:'603202',confidence:'high'},
    'Gummidipoondi': {apt:[22,39],house:[17,78],villa:[28,126],land:[7,34],trend:'+12.0%',sqft:2150,pincode:'601201',confidence:'low'},
    'Irungattukottai': {apt:[34,55],house:[120,209],villa:[200,337],land:[50,91],trend:'+9.0%',sqft:3300,pincode:'602117',confidence:'low'},
    'Kamaraj Nagar Avadi': {apt:[48,72],house:[199,304],villa:[332,488],land:[83,132],trend:'+10.0%',sqft:4550,pincode:'600071',confidence:'low'},
    'Kanchipuram Town': {apt:[30,55],house:[82,209],villa:[136,337],land:[34,91],trend:'+9.0%',sqft:3050,pincode:'631501',confidence:'medium'},
    'Kattankulathur': {apt:[46,72],house:[139,262],villa:[232,422],land:[58,114],trend:'+10.0%',sqft:4400,pincode:'603203',confidence:'medium'},
    'Kelambakkam': {apt:[60,87],house:[190,262],villa:[316,422],land:[79,114],trend:'+10.0%',sqft:5700,pincode:'603103',confidence:'medium'},
    'Kodungaiyur': {apt:[60,94],house:[247,391],villa:[412,629],land:[103,170],trend:'+9.0%',sqft:5900,pincode:'600118',confidence:'low'},
    'Korattur': {apt:[79,114],house:[329,471],villa:[548,758],land:[137,205],trend:'+8.0%',sqft:7400,pincode:'600080',confidence:'medium'},
    'Kovalam ECR': {apt:[60,103],house:[247,471],villa:[412,758],land:[103,205],trend:'+10.0%',sqft:6200,pincode:'603112',confidence:'low'},
    'Kundrathur': {apt:[51,79],house:[218,343],villa:[364,551],land:[91,149],trend:'+9.0%',sqft:4950,pincode:'600069',confidence:'low'},
    'Madanandapuram': {apt:[60,87],house:[247,368],villa:[412,592],land:[103,160],trend:'+9.0%',sqft:5700,pincode:'600125',confidence:'low'},
    'Madhavaram': {apt:[66,103],house:[274,430],villa:[456,692],land:[114,187],trend:'+9.0%',sqft:6450,pincode:'600060',confidence:'high'},
    'Madhavaram Milk Colony': {apt:[70,106],house:[286,446],villa:[476,718],land:[119,194],trend:'+9.0%',sqft:6650,pincode:'600051',confidence:'medium'},
    'Mahindra World City': {apt:[68,90],house:[110,237],villa:[184,381],land:[46,103],trend:'+10.0%',sqft:5900,pincode:'603004',confidence:'high'},
    'Mambakkam': {apt:[55,82],house:[206,327],villa:[344,525],land:[86,142],trend:'+10.0%',sqft:5200,pincode:'600127',confidence:'low'},
    'Manali': {apt:[51,82],house:[206,343],villa:[344,551],land:[86,149],trend:'+9.0%',sqft:4950,pincode:'600068',confidence:'medium'},
    'Manali New Town': {apt:[48,79],house:[190,315],villa:[316,507],land:[79,137],trend:'+9.0%',sqft:4750,pincode:'600103',confidence:'low'},
    'Mangadu': {apt:[55,82],house:[230,356],villa:[384,574],land:[96,155],trend:'+9.0%',sqft:5200,pincode:'600122',confidence:'medium'},
    'Maraimalai Nagar': {apt:[42,66],house:[67,156],villa:[112,252],land:[28,68],trend:'+10.0%',sqft:4000,pincode:'603209',confidence:'medium'},
    'Mathur': {apt:[48,75],house:[190,304],villa:[316,488],land:[79,132],trend:'+9.0%',sqft:4550,pincode:'600068',confidence:'low'},
    'Minjur': {apt:[27,46],house:[48,124],villa:[80,200],land:[20,54],trend:'+12.0%',sqft:2650,pincode:'601203',confidence:'low'},
    'Mogappair': {apt:[90,133],house:[384,577],villa:[640,929],land:[160,251],trend:'+8.0%',sqft:8550,pincode:'600037',confidence:'medium'},
    'Mogappair West': {apt:[84,127],house:[372,552],villa:[620,888],land:[155,240],trend:'+8.0%',sqft:8100,pincode:'600037',confidence:'medium'},
    'Mudichur': {apt:[51,75],house:[206,315],villa:[344,507],land:[86,137],trend:'+8.0%',sqft:4750,pincode:'600048',confidence:'low'},
    'Nolambur': {apt:[84,121],house:[358,513],villa:[596,825],land:[149,223],trend:'+8.0%',sqft:7800,pincode:'600095',confidence:'low'},
    'Oragadam': {apt:[42,66],house:[154,251],villa:[256,403],land:[64,109],trend:'+9.0%',sqft:4000,pincode:'602105',confidence:'medium'},
    'Ottiambakkam': {apt:[55,82],house:[206,327],villa:[344,525],land:[86,142],trend:'+10.0%',sqft:5200,pincode:'600130',confidence:'low'},
    'Padappai': {apt:[34,58],house:[82,182],villa:[136,292],land:[34,79],trend:'+10.0%',sqft:3300,pincode:'601301',confidence:'low'},
    'Padi': {apt:[72,109],house:[300,460],villa:[500,740],land:[125,200],trend:'+8.0%',sqft:6850,pincode:'600050',confidence:'low'},
    'Padur': {apt:[66,94],house:[154,221],villa:[256,355],land:[64,96],trend:'+10.0%',sqft:6200,pincode:'603103',confidence:'medium'},
    'Pallavaram': {apt:[72,114],house:[329,524],villa:[548,844],land:[137,228],trend:'+8.0%',sqft:7100,pincode:'600043',confidence:'high'},
    'Pammal': {apt:[60,90],house:[262,391],villa:[436,629],land:[109,170],trend:'+8.0%',sqft:5700,pincode:'600075',confidence:'medium'},
    'Paruthipattu': {apt:[48,72],house:[199,304],villa:[332,488],land:[83,132],trend:'+10.0%',sqft:4550,pincode:'600071',confidence:'low'},
    'Pattabiram': {apt:[46,70],house:[190,294],villa:[316,474],land:[79,128],trend:'+10.0%',sqft:4400,pincode:'600072',confidence:'low'},
    'Periyapalayam': {apt:[20,34],house:[17,71],villa:[28,115],land:[7,31],trend:'+12.0%',sqft:1900,pincode:'601102',confidence:'low'},
    'Perungalathur': {apt:[51,75],house:[206,315],villa:[344,507],land:[86,137],trend:'+8.0%',sqft:4750,pincode:'600063',confidence:'medium'},
    'Ponmar': {apt:[48,72],house:[175,274],villa:[292,440],land:[73,119],trend:'+10.0%',sqft:4550,pincode:'600048',confidence:'low'},
    'Ponneri': {apt:[22,36],house:[34,94],villa:[56,152],land:[14,41],trend:'+12.0%',sqft:2100,pincode:'601204',confidence:'medium'},
    'Poonamallee': {apt:[55,82],house:[247,368],villa:[412,592],land:[103,160],trend:'+12.0%',sqft:5200,pincode:'600056',confidence:'high'},
    'Potheri': {apt:[55,84],house:[190,315],villa:[316,507],land:[79,137],trend:'+10.0%',sqft:5200,pincode:'603203',confidence:'medium'},
    'Puzhal': {apt:[46,70],house:[190,288],villa:[316,462],land:[79,125],trend:'+9.0%',sqft:4400,pincode:'600066',confidence:'low'},
    'Sathangadu': {apt:[46,72],house:[175,288],villa:[292,462],land:[73,125],trend:'+9.0%',sqft:4400,pincode:'600019',confidence:'low'},
    'Selaiyur': {apt:[60,90],house:[247,377],villa:[412,607],land:[103,164],trend:'+8.0%',sqft:5700,pincode:'600073',confidence:'low'},
    'Sembakkam': {apt:[60,90],house:[247,377],villa:[412,607],land:[103,164],trend:'+8.0%',sqft:5700,pincode:'600073',confidence:'low'},
    'Sevvapet': {apt:[18,32],house:[19,71],villa:[32,115],land:[8,31],trend:'+12.0%',sqft:1800,pincode:'602025',confidence:'low'},
    'Singaperumal Koil': {apt:[42,75],house:[67,156],villa:[112,252],land:[28,68],trend:'+10.0%',sqft:4300,pincode:'603204',confidence:'high'},
    'Sriperumbudur': {apt:[42,66],house:[163,262],villa:[272,422],land:[68,114],trend:'+9.0%',sqft:4000,pincode:'602105',confidence:'medium'},
    'Surapet': {apt:[55,84],house:[218,356],villa:[364,574],land:[91,155],trend:'+9.0%',sqft:5200,pincode:'600066',confidence:'low'},
    'Tambaram': {apt:[60,97],house:[247,409],villa:[412,659],land:[103,178],trend:'+8.0%',sqft:5900,pincode:'600045',confidence:'high'},
    'Tambaram West': {apt:[58,87],house:[230,368],villa:[384,592],land:[96,160],trend:'+8.0%',sqft:5500,pincode:'600045',confidence:'medium'},
    'Thalambur': {apt:[70,97],house:[218,304],villa:[364,488],land:[91,132],trend:'+10.0%',sqft:6450,pincode:'600130',confidence:'medium'},
    'Thirumazhisai': {apt:[46,70],house:[175,274],villa:[292,440],land:[73,119],trend:'+12.0%',sqft:4300,pincode:'600124',confidence:'medium'},
    'Thirumudivakkam': {apt:[51,79],house:[206,327],villa:[344,525],land:[86,142],trend:'+9.0%',sqft:4950,pincode:'600132',confidence:'low'},
    'Thirumullaivoyal': {apt:[53,75],house:[247,343],villa:[412,551],land:[103,149],trend:'+10.0%',sqft:5400,pincode:'600062',confidence:'high'},
    'Thiruninravur': {apt:[24,36],house:[98,156],villa:[164,252],land:[41,68],trend:'+12.0%',sqft:2150,pincode:'602024',confidence:'medium'},
    'Thiruporur': {apt:[42,66],house:[120,237],villa:[200,381],land:[50,103],trend:'+10.0%',sqft:4000,pincode:'603110',confidence:'low'},
    'Thiruverkadu': {apt:[55,82],house:[218,327],villa:[364,525],land:[91,142],trend:'+12.0%',sqft:5200,pincode:'600077',confidence:'low'},
    'Tiruvallur Town': {apt:[27,46],house:[31,122],villa:[52,196],land:[13,53],trend:'+12.0%',sqft:2650,pincode:'602001',confidence:'medium'},
    'Urapakkam': {apt:[46,70],house:[190,288],villa:[316,462],land:[79,125],trend:'+10.0%',sqft:4400,pincode:'603210',confidence:'medium'},
    'Uthukottai': {apt:[17,30],house:[14,67],villa:[24,107],land:[6,29],trend:'+12.0%',sqft:1700,pincode:'602026',confidence:'low'},
    'Vandalur': {apt:[46,70],house:[175,274],villa:[292,440],land:[73,119],trend:'+10.0%',sqft:4300,pincode:'600048',confidence:'medium'},
    'Veppampattu': {apt:[22,35],house:[89,147],villa:[148,237],land:[37,64],trend:'+12.0%',sqft:2100,pincode:'602024',confidence:'low'},
    'Walajabad': {apt:[20,34],house:[43,115],villa:[72,185],land:[18,50],trend:'+9.0%',sqft:1900,pincode:'631605',confidence:'low'},
    // ── MANUAL / NOT IN CSV ──
    // 'Valmiki nagar' removed — not in seed CSV; resolves to parent Thiruvanmiyur
    // 'Vaishnavi nagar' removed — not in seed CSV; resolves to parent Thirumullaivoyal
    'Mylapore': {apt:[55,85],house:[290,440],villa:[480,720],land:[115,175],trend:'+5.0%',sqft:5100,pincode:'600004',confidence:'low'},
    'Mandaveli': {apt:[58,90],house:[300,450],villa:[500,750],land:[120,180],trend:'+5.2%',sqft:5300,pincode:'600028',confidence:'low'},
    'R.A. Puram': {apt:[78,122],house:[440,660],villa:[700,1050],land:[165,245],trend:'+5.0%',sqft:6500,pincode:'600028',confidence:'low'},
    'Boat Club Road': {apt:[120,200],house:[700,1100],villa:[1200,1800],land:[280,420],trend:'+3.5%',sqft:11000,pincode:'600028',confidence:'low'},
    'Kilpauk': {apt:[50,80],house:[245,368],villa:[420,630],land:[105,158],trend:'+6.0%',sqft:4800,pincode:'600010',confidence:'low'},
    'Manapakkam': {apt:[30,48],house:[115,170],villa:[195,290],land:[52,78],trend:'+10.8%',sqft:3500,pincode:'600125',confidence:'low'},
    'Madambakkam': {apt:[23,38],house:[88,132],villa:[158,235],land:[40,60],trend:'+12.5%',sqft:3000,pincode:'600126',confidence:'low'},
    'Ekkattuthangal': {apt:[40,64],house:[170,255],villa:[295,440],land:[75,113],trend:'+7.5%',sqft:4200,pincode:'600032',confidence:'low'},
    'Ambattur OT': {apt:[57,89],house:[257,400],villa:[428,666],land:[98,159],trend:'+13.0%',sqft:5500,pincode:'600053',confidence:'low'},
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
/* Locality tier classification — drives section B narrative. */
const LOCALITY_TIER = {
  // ── Chennai ── (rebuilt from CSV GCC zone classification)
  'Adyar':'premium',
  'Akkarai':'premium',
  'Alwarpet':'premium',
  'Aminjikarai':'premium',
  'Anna Nagar':'premium',
  'Anna Nagar West':'premium',
  'Ashok Nagar':'premium',
  'Besant Nagar':'premium',
  'Boat Club Road':'premium',
  'Chetpet':'premium',
  'Choolaimedu':'premium',
  'Egmore':'premium',
  'Gopalapuram':'premium',
  'Guindy':'premium',
  'Injambakkam':'premium',
  'KK Nagar':'premium',
  'Kilpauk':'premium',
  'Kodambakkam':'premium',
  'Kolathur':'premium',
  'Kottivakkam':'premium',
  'Kotturpuram':'premium',
  'MGR Nagar':'premium',
  'Mandaveli':'premium',
  'Mylapore':'premium',
  'Neelankarai':'premium',
  'Nesapakkam':'premium',
  'Nungambakkam':'premium',
  'Palavakkam':'premium',
  'Periyar Nagar':'premium',
  'Purasawalkam':'premium',
  'R.A. Puram':'premium',
  'Royapettah':'premium',
  'Saidapet':'premium',
  'Saligramam':'premium',
  'Shenoy Nagar':'premium',
  'T Nagar':'premium',
  'Teynampet':'premium',
  'Thiruvanmiyur':'premium',
  'Thousand Lights':'premium',
  'Triplicane':'premium',
  'Uthandi':'premium',
  'Vadapalani':'premium',
  'Velachery':'premium',
  'Vepery':'premium',
  'Villivakkam':'premium',
  'Adambakkam':'established',
  'Alandur':'established',
  'Alwarthirunagar':'established',
  'Ayanavaram':'established',
  'Choolai':'established',
  'Erukkancherry':'established',
  'Iyyappanthangal':'established',
  'Kosapet':'established',
  'Maduravoyal':'established',
  'Mannady':'established',
  'Meenambakkam':'established',
  'Nanganallur':'established',
  'Otteri':'established',
  'Parrys':'established',
  'Pazhavanthangal':'established',
  'Perambur':'established',
  'Porur':'established',
  'Pulianthope':'established',
  'Ramapuram':'established',
  'Royapuram':'established',
  'Sembium':'established',
  'Sowcarpet':'established',
  'St Thomas Mount':'established',
  'Valasaravakkam':'established',
  'Virugambakkam':'established',
  'Washermanpet':'established',
  'Ekkattuthangal':'emerging',
  'Karapakkam':'emerging',
  'Keelkattalai':'emerging',
  'Kovilambakkam':'emerging',
  'Madipakkam':'emerging',
  'Manapakkam':'emerging',
  'Medavakkam':'emerging',
  'Navalur':'emerging',
  'Pallikaranai':'emerging',
  'Perumbakkam':'emerging',
  'Perungudi':'emerging',
  'Semmancheri':'emerging',
  'Sholinganallur':'emerging',
  'Siruseri':'emerging',
  'Sithalapakkam':'emerging',
  'Taramani':'emerging',
  'Thoraipakkam':'emerging',
  'Ambattur':'peripheral',
  'Ambattur OT':'peripheral',
  'Anakaputhur':'peripheral',
  'Anna Nagar West Extn':'peripheral',
  'Arakkonam':'peripheral',
  'Avadi':'peripheral',
  'Ayappakkam':'peripheral',
  'Chengalpattu Town':'peripheral',
  'Chromepet':'peripheral',
  'East Tambaram':'peripheral',
  'Ennore':'peripheral',
  'Guduvanchery':'peripheral',
  'Gummidipoondi':'peripheral',
  'Irungattukottai':'peripheral',
  'Kaladipet':'peripheral',
  'Kamaraj Nagar Avadi':'peripheral',
  'Kanchipuram Town':'peripheral',
  'Kathivakkam':'peripheral',
  'Kattankulathur':'peripheral',
  'Kelambakkam':'peripheral',
  'Kodungaiyur':'peripheral',
  'Korattur':'peripheral',
  'Korukkupet':'peripheral',
  'Kovalam ECR':'peripheral',
  'Kundrathur':'peripheral',
  'Madambakkam':'peripheral',
  'Madanandapuram':'peripheral',
  'Madhavaram':'peripheral',
  'Madhavaram Milk Colony':'peripheral',
  'Mahindra World City':'peripheral',
  'Mambakkam':'peripheral',
  'Manali':'peripheral',
  'Manali New Town':'peripheral',
  'Mangadu':'peripheral',
  'Maraimalai Nagar':'peripheral',
  'Mathur':'peripheral',
  'Minjur':'peripheral',
  'Mogappair':'peripheral',
  'Mogappair West':'peripheral',
  'Mudichur':'peripheral',
  'Nolambur':'peripheral',
  'Old Washermanpet':'peripheral',
  'Oragadam':'peripheral',
  'Ottiambakkam':'peripheral',
  'Padappai':'peripheral',
  'Padi':'peripheral',
  'Padur':'peripheral',
  'Pallavaram':'peripheral',
  'Pammal':'peripheral',
  'Paruthipattu':'peripheral',
  'Pattabiram':'peripheral',
  'Periyapalayam':'peripheral',
  'Perungalathur':'peripheral',
  'Ponmar':'peripheral',
  'Ponneri':'peripheral',
  'Poonamallee':'peripheral',
  'Potheri':'peripheral',
  'Puzhal':'peripheral',
  'Sathangadu':'peripheral',
  'Selaiyur':'peripheral',
  'Sembakkam':'peripheral',
  'Sevvapet':'peripheral',
  'Singaperumal Koil':'peripheral',
  'Sriperumbudur':'peripheral',
  'Surapet':'peripheral',
  'Tambaram':'peripheral',
  'Tambaram West':'peripheral',
  'Thalambur':'peripheral',
  'Thirumazhisai':'peripheral',
  'Thirumudivakkam':'peripheral',
  'Thirumullaivoyal':'peripheral',
  'Thiruninravur':'peripheral',
  'Thiruporur':'peripheral',
  'Thiruverkadu':'peripheral',
  'Tiruvallur Town':'peripheral',
  'Tiruvottiyur':'peripheral',
  'Tollgate':'peripheral',
  'Tondiarpet':'peripheral',
  'Urapakkam':'peripheral',
  'Uthukottai':'peripheral',
  'Vandalur':'peripheral',
  'Veppampattu':'peripheral',
  'Vyasarpadi':'peripheral',
  'Walajabad':'peripheral',
  'Wimco Nagar':'peripheral',
  // ── Bangalore ── (unchanged)
  'Indiranagar':'premium',
  'Koramangala':'premium',
  'Jayanagar':'premium',
  'Sadashivanagar':'premium',
  'Malleshwaram':'premium',
  'Frazer Town':'premium',
  'Cooke Town':'premium',
  'Richmond Town':'premium',
  'Lavelle Road':'premium',
  'Basavanagudi':'premium',
  'HSR Layout':'established',
  'Hebbal':'established',
  'BTM Layout':'established',
  'JP Nagar':'established',
  'Rajajinagar':'established',
  'Banashankari':'established',
  'Vijayanagar':'established',
  'Whitefield':'emerging',
  'Marathahalli':'emerging',
  'Sarjapur Road':'emerging',
  'Bellandur':'emerging',
  'Mahadevapura':'emerging',
  'ITPL Main Road':'emerging',
  'Doddanekundi':'emerging',
  'Bommanahalli':'emerging',
  'Electronic City':'peripheral',
  'Yelahanka':'peripheral',
  'Devanahalli':'peripheral',
  'Hennur':'peripheral',
  'Banaswadi':'peripheral',
  'KR Puram':'peripheral',
  'Begur':'peripheral',
  'Hulimavu':'peripheral',
  'Bannerghatta Road':'peripheral',
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

  // Always submit fresh — never reuse a stale valId from a prior estimate.
  // Without this, the previous estimate's teaser shows for the new property.
  sessionStorage.removeItem('valuprop_val_id');
  sessionStorage.removeItem('valuprop_prop_id');
  trySubmitBackend(search);
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

/* ─── Fuzzy string matching (Levenshtein) ───────────────────────
 * Used in lookupLocality to handle typos and minor name variants.
 */
function _levenshtein(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({length: m + 1}, (_, i) =>
    Array.from({length: n + 1}, (_, j) => i === 0 ? j : j === 0 ? i : 0)
  );
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i-1] === b[j-1] ? dp[i-1][j-1]
        : 1 + Math.min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]);
  return dp[m][n];
}
function _strSim(a, b) {
  if (!a || !b) return 0;
  return 1 - _levenshtein(a, b) / Math.max(a.length, b.length);
}

/* Collapses Tamil-English transliteration variants so phonetic spellings
   match: Th->T, double->single consonant, zh->l, oo->u, punctuation stripped.
   Makes "tirumullaivoyal" and "thirumullaivoyal" identical. */
function _normLoc(s) {
  return (s || '')
    .toLowerCase().trim()
    .replace(/\bth/g, 't')        // word-initial Th -> T
    .replace(/th/g, 't')          // internal th -> t
    .replace(/zh/g, 'l')          // Tamil zh -> l
    .replace(/oo/g, 'u')          // oo -> u
    .replace(/([a-z])\1+/g, '$1') // collapse doubled letters
    .replace(/[^a-z0-9 ]/g, '')   // strip punctuation
    .replace(/\s+/g, ' ')
    .trim();
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
/* Normalize city: handles cases where user types a sub-area or locality
 * name in the city field (e.g. "tiruvanmiyur" instead of "Chennai").
 * Checks PRICE_DB keys first, then scans all locality names across cities.
 */
function normalizeCity(city) {
  if (!city) return 'Chennai';
  // Direct match (already a valid PRICE_DB city key)
  if (PRICE_DB[city]) return city;
  // Case-insensitive city key match
  const cityLower = city.toLowerCase().trim();
  for (const c of Object.keys(PRICE_DB)) {
    if (c.toLowerCase() === cityLower) return c;
  }
  // Check if the value is actually a locality name within a city
  // e.g. "tiruvanmiyur" → found as locality key in Chennai → return "Chennai"
  for (const [c, db] of Object.entries(PRICE_DB)) {
    for (const loc of Object.keys(db)) {
      if (loc.toLowerCase() === cityLower) return c;
    }
  }
  // Default to Chennai
  return 'Chennai';
}

function lookupLocality(city, locality, pincode) {
  const normCity = normalizeCity(city);
  const cityDb = PRICE_DB[normCity];
  if (!cityDb) return cityAverageLookup('Chennai');

  // Split ALL comma-parts (mirror backend get_locality), not just the first.
  const parts = locality
    ? locality.split(',').map(p => p.trim()).filter(Boolean)
    : [];

  // ── Step 1: Exact match (transliteration-normalised) over ALL parts ──
  for (const part of parts) {
    const needle = _normLoc(part);
    for (const key of Object.keys(cityDb)) {
      if (_normLoc(key) === needle) {
        return { db: cityDb[key], matched: key, source: 'exact' };
      }
    }
  }

  // ── Step 2: Pincode match — BEFORE fuzzy, so a reliable pincode wins ──
  if (pincode) {
    const pinClean = String(pincode).trim();
    for (const key of Object.keys(cityDb)) {
      if (cityDb[key].pincode === pinClean) {
        return { db: cityDb[key], matched: key, source: 'pincode' };
      }
    }
  }

  // ── Step 3: Fuzzy over ALL parts — keep the single best, normalised ──
  let bestKey = null, bestSim = 0;
  for (const part of parts) {
    const needle = _normLoc(part);
    for (const key of Object.keys(cityDb)) {
      const sim = _strSim(needle, _normLoc(key));
      if (sim > bestSim) { bestSim = sim; bestKey = key; }
    }
  }
  if (bestKey && bestSim >= 0.82) {          // raised from 0.72
    return { db: cityDb[bestKey], matched: bestKey, source: 'fuzzy' };
  }

  // ── Step 4: City-wide average (last resort) ──
  return cityAverageLookup(normCity);
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
    if(search.carpetArea){const a=parseInt(search.carpetArea),r=db.sqft;lo=Math.round(a*r*0.9/1e5);hi=Math.round(a*r*1.1/1e5);}
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
  if (s.carpetArea) facts.push(['Carpet area', `${parseInt(s.carpetArea).toLocaleString('en-IN')} sq.ft`]);
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

  // Confidence note — surfaces low-confidence rates honestly
  let confidenceNote = '';
  if (db.confidence === 'low' && source !== 'city_avg') {
    confidenceNote = `<p style="background:#fef9c3; border-left:3px solid #ca8a04; padding:8px 12px; font-size:12px; color:#854d0e; margin-bottom:10px;">
      <strong>Rate confidence: low.</strong> Our seed data for this micro-market is still being vetted against recent transactions. Treat ranges as directional. Your paid report cross-checks with live signals.</p>`;
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
    `${sourceNote}${confidenceNote}<p>${para1}</p><p>${para2}</p>`;
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
  // Guard: if backend never responded, re-submit so payment page has IDs
  if (!propId) {
    try {
      const r = await fetch(`${BACKEND_URL}/api/property/submit`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(search)});
      const d = await r.json();
      if(d.property_id) sessionStorage.setItem('valuprop_prop_id',d.property_id);
      if(d.valuation_id) sessionStorage.setItem('valuprop_val_id',d.valuation_id);
    }catch(e){}
  }
  window.location.href='payment.html';
}