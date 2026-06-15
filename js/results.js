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
    'Adyar': {apt:[184,241],house:[829,1086],villa:[1379,1807],land:[350,514],trend:'+5.5%',sqft:16500,pincode:'600020',confidence:'high'},
    'Akkarai': {apt:[121,178],house:[543,800],villa:[903,1331],land:[257,444],trend:'+5.5%',sqft:11500,pincode:'600119',confidence:'low'},
    'Alwarpet': {apt:[228,330],house:[1029,1486],villa:[1711,2472],land:[467,818],trend:'+5.5%',sqft:21000,pincode:'600018',confidence:'high'},
    'Aminjikarai': {apt:[108,159],house:[486,714],villa:[808,1188],land:[210,327],trend:'+5.5%',sqft:10000,pincode:'600029',confidence:'medium'},
    'Anna Nagar': {apt:[152,228],house:[686,1029],villa:[1141,1711],land:[304,491],trend:'+5.5%',sqft:14000,pincode:'600040',confidence:'high'},
    'Anna Nagar West': {apt:[127,184],house:[571,829],villa:[951,1379],land:[257,397],trend:'+5.5%',sqft:12000,pincode:'600101',confidence:'medium'},
    'Ashok Nagar': {apt:[127,184],house:[571,829],villa:[951,1379],land:[257,397],trend:'+5.5%',sqft:12000,pincode:'600083',confidence:'medium'},
    'Besant Nagar': {apt:[178,235],house:[800,1057],villa:[1331,1759],land:[374,537],trend:'+5.5%',sqft:16000,pincode:'600090',confidence:'high'},
    'Boat Club Road': {apt:[120,200],house:[700,1100],villa:[1200,1800],land:[280,420],trend:'+3.5%',sqft:11000,pincode:'600028',confidence:'low'},
    'Chetpet': {apt:[152,222],house:[686,1000],villa:[1141,1664],land:[304,467],trend:'+5.5%',sqft:14500,pincode:'600031',confidence:'medium'},
    'Choolaimedu': {apt:[102,146],house:[457,657],villa:[761,1093],land:[199,315],trend:'+5.5%',sqft:9500,pincode:'600094',confidence:'low'},
    'Egmore': {apt:[140,209],house:[629,943],villa:[1046,1569],land:[280,444],trend:'+5.5%',sqft:13500,pincode:'600008',confidence:'medium'},
    'Gopalapuram': {apt:[203,305],house:[914,1371],villa:[1521,2282],land:[420,701],trend:'+5.5%',sqft:19000,pincode:'600086',confidence:'medium'},
    'Guindy': {apt:[114,171],house:[514,771],villa:[856,1284],land:[210,327],trend:'+5.5%',sqft:11000,pincode:'600032',confidence:'medium'},
    'Injambakkam': {apt:[121,178],house:[543,800],villa:[903,1331],land:[234,420],trend:'+5.5%',sqft:11500,pincode:'600115',confidence:'medium'},
    'KK Nagar': {apt:[114,171],house:[514,771],villa:[856,1284],land:[234,374],trend:'+5.5%',sqft:11000,pincode:'600078',confidence:'medium'},
    'Kilpauk': {apt:[50,80],house:[245,368],villa:[420,630],land:[105,158],trend:'+6.0%',sqft:4800,pincode:'600010',confidence:'low'},
    'Kodambakkam': {apt:[114,171],house:[514,771],villa:[856,1284],land:[234,374],trend:'+5.5%',sqft:11000,pincode:'600024',confidence:'medium'},
    'Kolathur': {apt:[70,102],house:[314,457],villa:[523,761],land:[117,182],trend:'+5.5%',sqft:6500,pincode:'600099',confidence:'high'},
    'Kottivakkam': {apt:[140,197],house:[629,886],villa:[1046,1474],land:[280,444],trend:'+5.5%',sqft:13000,pincode:'600041',confidence:'medium'},
    'Kotturpuram': {apt:[152,222],house:[686,1000],villa:[1141,1664],land:[304,467],trend:'+5.5%',sqft:14500,pincode:'600085',confidence:'low'},
    'MGR Nagar': {apt:[95,140],house:[429,629],villa:[713,1046],land:[187,304],trend:'+5.5%',sqft:9000,pincode:'600078',confidence:'low'},
    'Mandaveli': {apt:[58,90],house:[300,450],villa:[500,750],land:[120,180],trend:'+5.2%',sqft:5300,pincode:'600028',confidence:'low'},
    'Mylapore': {apt:[55,85],house:[290,440],villa:[480,720],land:[115,175],trend:'+5.0%',sqft:5100,pincode:'600004',confidence:'low'},
    'Neelankarai': {apt:[127,197],house:[571,886],villa:[951,1474],land:[280,514],trend:'+5.5%',sqft:12500,pincode:'600115',confidence:'high'},
    'Nesapakkam': {apt:[102,146],house:[457,657],villa:[761,1093],land:[199,315],trend:'+5.5%',sqft:9500,pincode:'600078',confidence:'low'},
    'Nungambakkam': {apt:[190,279],house:[857,1257],villa:[1426,2092],land:[420,701],trend:'+5.5%',sqft:18000,pincode:'600034',confidence:'high'},
    'Palavakkam': {apt:[140,203],house:[629,914],villa:[1046,1521],land:[304,467],trend:'+5.5%',sqft:13000,pincode:'600041',confidence:'medium'},
    'Periyar Nagar': {apt:[82,127],house:[371,571],villa:[618,951],land:[152,245],trend:'+5.5%',sqft:8000,pincode:'600082',confidence:'low'},
    'Purasawalkam': {apt:[140,222],house:[629,1000],villa:[1046,1664],land:[280,444],trend:'+5.5%',sqft:14000,pincode:'600084',confidence:'high'},
    'R.A. Puram': {apt:[78,122],house:[440,660],villa:[700,1050],land:[165,245],trend:'+5.0%',sqft:6500,pincode:'600028',confidence:'low'},
    'Royapettah': {apt:[140,203],house:[629,914],villa:[1046,1521],land:[280,444],trend:'+5.5%',sqft:13000,pincode:'600014',confidence:'low'},
    'Saidapet': {apt:[102,159],house:[457,714],villa:[761,1188],land:[210,327],trend:'+5.5%',sqft:10000,pincode:'600015',confidence:'medium'},
    'Saligramam': {apt:[108,165],house:[486,743],villa:[808,1236],land:[210,327],trend:'+5.5%',sqft:10500,pincode:'600093',confidence:'low'},
    'Shenoy Nagar': {apt:[127,184],house:[571,829],villa:[951,1379],land:[257,374],trend:'+5.5%',sqft:12000,pincode:'600030',confidence:'medium'},
    'T Nagar': {apt:[203,266],house:[914,1200],villa:[1521,1997],land:[420,654],trend:'+5.5%',sqft:17000,pincode:'600017',confidence:'high'},
    'Teynampet': {apt:[190,292],house:[857,1314],villa:[1426,2187],land:[397,654],trend:'+5.5%',sqft:18000,pincode:'600018',confidence:'high'},
    'Thiruvanmiyur': {apt:[152,209],house:[686,943],villa:[1141,1569],land:[280,420],trend:'+5.5%',sqft:14000,pincode:'600041',confidence:'medium'},
    'Valmiki nagar': {apt:[152,209],house:[686,943],villa:[1141,1569],land:[280,420],trend:'+5.5%',sqft:14000,pincode:'600041',confidence:'medium'},
    'Vaishnavi nagar': {apt:[152,209],house:[686,943],villa:[1141,1569],land:[280,420],trend:'+5.5%',sqft:14000,pincode:'600041',confidence:'medium'},
    'Thousand Lights': {apt:[178,266],house:[800,1200],villa:[1331,1997],land:[374,607],trend:'+5.5%',sqft:17000,pincode:'600006',confidence:'low'},
    'Triplicane': {apt:[102,165],house:[457,743],villa:[761,1236],land:[199,339],trend:'+5.5%',sqft:10000,pincode:'600005',confidence:'medium'},
    'Uthandi': {apt:[102,159],house:[457,714],villa:[761,1188],land:[187,350],trend:'+5.5%',sqft:10000,pincode:'600119',confidence:'low'},
    'Vadapalani': {apt:[121,178],house:[543,800],villa:[903,1331],land:[234,374],trend:'+5.5%',sqft:11500,pincode:'600026',confidence:'medium'},
    'Velachery': {apt:[100,168],house:[449,757],villa:[746,1260],land:[187,280],trend:'+5.5%',sqft:9500,pincode:'600042',confidence:'high'},
    'Vepery': {apt:[127,203],house:[571,914],villa:[951,1521],land:[234,397],trend:'+5.5%',sqft:13000,pincode:'600007',confidence:'low'},
    'Villivakkam': {apt:[89,133],house:[400,600],villa:[666,998],land:[187,304],trend:'+5.5%',sqft:8500,pincode:'600049',confidence:'medium'},
    // ── ESTABLISHED ──
    'Adambakkam': {apt:[95,140],house:[429,629],villa:[713,1046],land:[175,280],trend:'+7.5%',sqft:9000,pincode:'600088',confidence:'medium'},
    'Alandur': {apt:[114,171],house:[514,771],villa:[856,1284],land:[222,362],trend:'+7.5%',sqft:11000,pincode:'600016',confidence:'medium'},
    'Alwarthirunagar': {apt:[89,133],house:[400,600],villa:[666,998],land:[164,257],trend:'+7.5%',sqft:8500,pincode:'600087',confidence:'low'},
    'Ayanavaram': {apt:[89,133],house:[400,600],villa:[666,998],land:[164,257],trend:'+7.5%',sqft:8500,pincode:'600023',confidence:'medium'},
    'Choolai': {apt:[86,133],house:[389,600],villa:[647,998],land:[152,245],trend:'+7.5%',sqft:8500,pincode:'600112',confidence:'low'},
    'Erukkancherry': {apt:[61,95],house:[274,429],villa:[456,713],land:[105,168],trend:'+7.5%',sqft:5800,pincode:'600118',confidence:'low'},
    'Iyyappanthangal': {apt:[70,108],house:[314,486],villa:[523,808],land:[117,187],trend:'+7.5%',sqft:6800,pincode:'600056',confidence:'medium'},
    'Kosapet': {apt:[82,127],house:[371,571],villa:[618,951],land:[145,234],trend:'+7.5%',sqft:8000,pincode:'600012',confidence:'low'},
    'Maduravoyal': {apt:[82,121],house:[371,543],villa:[618,903],land:[140,222],trend:'+7.5%',sqft:7800,pincode:'600095',confidence:'low'},
    'Mannady': {apt:[114,190],house:[514,857],villa:[856,1426],land:[210,362],trend:'+7.5%',sqft:11500,pincode:'600001',confidence:'low'},
    'Meenambakkam': {apt:[82,121],house:[371,543],villa:[618,903],land:[152,234],trend:'+7.5%',sqft:7800,pincode:'600027',confidence:'low'},
    'Nanganallur': {apt:[102,152],house:[457,686],villa:[761,1141],land:[187,304],trend:'+7.5%',sqft:9500,pincode:'600061',confidence:'medium'},
    'Otteri': {apt:[82,127],house:[371,571],villa:[618,951],land:[152,245],trend:'+7.5%',sqft:8000,pincode:'600012',confidence:'low'},
    'Parrys': {apt:[108,184],house:[486,829],villa:[808,1379],land:[199,350],trend:'+7.5%',sqft:11000,pincode:'600001',confidence:'low'},
    'Pazhavanthangal': {apt:[102,152],house:[457,686],villa:[761,1141],land:[187,304],trend:'+7.5%',sqft:9500,pincode:'600114',confidence:'low'},
    'Perambur': {apt:[82,127],house:[371,571],villa:[618,951],land:[140,222],trend:'+7.5%',sqft:8000,pincode:'600011',confidence:'medium'},
    'Porur': {apt:[95,140],house:[429,629],villa:[713,1046],land:[164,269],trend:'+7.5%',sqft:9000,pincode:'600116',confidence:'high'},
    'Pulianthope': {apt:[70,108],house:[314,486],villa:[523,808],land:[121,192],trend:'+7.5%',sqft:6800,pincode:'600012',confidence:'low'},
    'Ramapuram': {apt:[89,133],house:[400,600],villa:[666,998],land:[159,245],trend:'+7.5%',sqft:8500,pincode:'600089',confidence:'medium'},
    'Royapuram': {apt:[127,209],house:[571,943],villa:[951,1569],land:[222,374],trend:'+7.5%',sqft:13000,pincode:'600013',confidence:'high'},
    'Sembium': {apt:[76,121],house:[343,543],villa:[570,903],land:[135,215],trend:'+7.5%',sqft:7500,pincode:'600011',confidence:'low'},
    'Sowcarpet': {apt:[121,209],house:[543,943],villa:[903,1569],land:[234,409],trend:'+7.5%',sqft:12500,pincode:'600079',confidence:'low'},
    'St Thomas Mount': {apt:[108,159],house:[486,714],villa:[808,1188],land:[199,315],trend:'+7.5%',sqft:10000,pincode:'600016',confidence:'low'},
    'Valasaravakkam': {apt:[89,133],house:[400,600],villa:[666,998],land:[164,257],trend:'+7.5%',sqft:8500,pincode:'600087',confidence:'medium'},
    'Virugambakkam': {apt:[102,152],house:[457,686],villa:[761,1141],land:[199,315],trend:'+7.5%',sqft:9500,pincode:'600092',confidence:'medium'},
    'Washermanpet': {apt:[82,133],house:[371,600],villa:[618,998],land:[140,234],trend:'+7.5%',sqft:8200,pincode:'600021',confidence:'medium'},
    // ── EMERGING ──
    'Ekkattuthangal': {apt:[40,64],house:[170,255],villa:[295,440],land:[75,113],trend:'+7.5%',sqft:4200,pincode:'600032',confidence:'low'},
    'Karapakkam': {apt:[121,165],house:[543,743],villa:[903,1236],land:[140,192],trend:'+10.5%',sqft:11000,pincode:'600097',confidence:'medium'},
    'Keelkattalai': {apt:[74,102],house:[331,457],villa:[551,761],land:[112,159],trend:'+10.5%',sqft:6800,pincode:'600117',confidence:'low'},
    'Kovilambakkam': {apt:[70,99],house:[314,446],villa:[523,742],land:[105,152],trend:'+10.5%',sqft:6500,pincode:'600129',confidence:'low'},
    'Madipakkam': {apt:[76,112],house:[343,503],villa:[570,837],land:[128,182],trend:'+10.5%',sqft:7200,pincode:'600091',confidence:'medium'},
    'Manapakkam': {apt:[30,48],house:[115,170],villa:[195,290],land:[52,78],trend:'+10.8%',sqft:3500,pincode:'600125',confidence:'low'},
    'Medavakkam': {apt:[70,104],house:[314,469],villa:[523,780],land:[105,159],trend:'+10.5%',sqft:6800,pincode:'600100',confidence:'high'},
    'Navalur': {apt:[86,121],house:[389,543],villa:[647,903],land:[140,199],trend:'+10.5%',sqft:7800,pincode:'600130',confidence:'high'},
    'Pallikaranai': {apt:[82,121],house:[371,543],villa:[618,903],land:[128,182],trend:'+10.5%',sqft:7800,pincode:'600100',confidence:'medium'},
    'Perumbakkam': {apt:[82,117],house:[371,526],villa:[618,875],land:[128,175],trend:'+10.5%',sqft:7800,pincode:'600100',confidence:'high'},
    'Perungudi': {apt:[171,228],house:[771,1029],villa:[1284,1711],land:[152,199],trend:'+10.5%',sqft:15500,pincode:'600096',confidence:'high'},
    'Semmancheri': {apt:[70,99],house:[314,446],villa:[523,742],land:[93,135],trend:'+10.5%',sqft:6500,pincode:'600119',confidence:'low'},
    'Sholinganallur': {apt:[108,159],house:[486,714],villa:[808,1188],land:[135,182],trend:'+10.5%',sqft:10000,pincode:'600119',confidence:'high'},
    'Siruseri': {apt:[76,108],house:[343,486],villa:[570,808],land:[98,140],trend:'+10.5%',sqft:7000,pincode:'603103',confidence:'high'},
    'Sithalapakkam': {apt:[63,91],house:[286,411],villa:[475,685],land:[93,135],trend:'+10.5%',sqft:6000,pincode:'600126',confidence:'low'},
    'Taramani': {apt:[127,190],house:[571,857],villa:[951,1426],land:[164,234],trend:'+10.5%',sqft:12500,pincode:'600113',confidence:'medium'},
    'Thoraipakkam': {apt:[140,197],house:[629,886],villa:[1046,1474],land:[140,182],trend:'+10.5%',sqft:13000,pincode:'600097',confidence:'high'},
    // ── PERIPHERAL ──
    'Ambattur': {apt:[63,95],house:[286,429],villa:[475,713],land:[112,168],trend:'+13.0%',sqft:6000,pincode:'600053',confidence:'high'},
    'Ambattur OT': {apt:[57,89],house:[257,400],villa:[428,666],land:[98,159],trend:'+13.0%',sqft:5500,pincode:'600053',confidence:'low'},
    'Anakaputhur': {apt:[57,89],house:[257,400],villa:[428,666],land:[98,159],trend:'+13.0%',sqft:5500,pincode:'600070',confidence:'low'},
    'Anna Nagar West Extn': {apt:[108,165],house:[486,743],villa:[808,1236],land:[187,304],trend:'+13.0%',sqft:10500,pincode:'600101',confidence:'medium'},
    'Arakkonam': {apt:[28,48],house:[126,217],villa:[209,361],land:[28,65],trend:'+13.0%',sqft:2800,pincode:'631001',confidence:'low'},
    'Avadi': {apt:[51,79],house:[229,354],villa:[380,589],land:[89,140],trend:'+13.0%',sqft:5000,pincode:'600054',confidence:'high'},
    'Ayappakkam': {apt:[57,89],house:[257,400],villa:[428,666],land:[98,159],trend:'+13.0%',sqft:5500,pincode:'600077',confidence:'low'},
    'Chengalpattu Town': {apt:[38,66],house:[171,297],villa:[285,494],land:[47,105],trend:'+13.0%',sqft:3800,pincode:'603001',confidence:'medium'},
    'Chromepet': {apt:[76,114],house:[343,514],villa:[570,856],land:[135,210],trend:'+13.0%',sqft:7200,pincode:'600044',confidence:'high'},
    'East Tambaram': {apt:[61,91],house:[274,411],villa:[456,685],land:[98,164],trend:'+13.0%',sqft:5800,pincode:'600059',confidence:'low'},
    'Ennore': {apt:[57,89],house:[257,400],villa:[428,666],land:[93,152],trend:'+13.0%',sqft:5500,pincode:'600057',confidence:'low'},
    'Guduvanchery': {apt:[48,74],house:[217,331],villa:[361,551],land:[75,121],trend:'+13.0%',sqft:4500,pincode:'603202',confidence:'high'},
    'Gummidipoondi': {apt:[23,41],house:[103,183],villa:[171,304],land:[8,35],trend:'+13.0%',sqft:2300,pincode:'601201',confidence:'low'},
    'Irungattukottai': {apt:[36,57],house:[160,257],villa:[266,428],land:[51,93],trend:'+13.0%',sqft:3500,pincode:'602117',confidence:'low'},
    'Kaladipet': {apt:[74,112],house:[331,503],villa:[551,837],land:[121,192],trend:'+13.0%',sqft:7000,pincode:'600019',confidence:'low'},
    'Kamaraj Nagar Avadi': {apt:[51,76],house:[229,343],villa:[380,570],land:[84,135],trend:'+13.0%',sqft:4800,pincode:'600071',confidence:'low'},
    'Kanchipuram Town': {apt:[32,57],house:[143,257],villa:[238,428],land:[35,93],trend:'+13.0%',sqft:3200,pincode:'631501',confidence:'medium'},
    'Kathivakkam': {apt:[53,82],house:[240,371],villa:[399,618],land:[89,145],trend:'+13.0%',sqft:5200,pincode:'600060',confidence:'low'},
    'Kattankulathur': {apt:[48,76],house:[217,343],villa:[361,570],land:[58,117],trend:'+13.0%',sqft:4600,pincode:'603203',confidence:'medium'},
    'Kelambakkam': {apt:[63,91],house:[286,411],villa:[475,685],land:[82,117],trend:'+13.0%',sqft:6000,pincode:'603103',confidence:'medium'},
    'Kodungaiyur': {apt:[63,99],house:[286,446],villa:[475,742],land:[105,175],trend:'+13.0%',sqft:6200,pincode:'600118',confidence:'low'},
    'Korattur': {apt:[82,121],house:[371,543],villa:[618,903],land:[140,210],trend:'+13.0%',sqft:7800,pincode:'600080',confidence:'medium'},
    'Korukkupet': {apt:[74,114],house:[331,514],villa:[551,856],land:[128,206],trend:'+13.0%',sqft:7200,pincode:'600021',confidence:'low'},
    'Kovalam ECR': {apt:[63,108],house:[286,486],villa:[475,808],land:[105,210],trend:'+13.0%',sqft:6500,pincode:'603112',confidence:'low'},
    'Kundrathur': {apt:[53,82],house:[240,371],villa:[399,618],land:[93,152],trend:'+13.0%',sqft:5200,pincode:'600069',confidence:'low'},
    'Madambakkam': {apt:[23,38],house:[88,132],villa:[158,235],land:[40,60],trend:'+12.5%',sqft:3000,pincode:'600126',confidence:'low'},
    'Madanandapuram': {apt:[63,91],house:[286,411],villa:[475,685],land:[105,164],trend:'+13.0%',sqft:6000,pincode:'600125',confidence:'low'},
    'Madhavaram': {apt:[70,108],house:[314,486],villa:[523,808],land:[117,192],trend:'+13.0%',sqft:6800,pincode:'600060',confidence:'high'},
    'Madhavaram Milk Colony': {apt:[74,112],house:[331,503],villa:[551,837],land:[121,199],trend:'+13.0%',sqft:7000,pincode:'600051',confidence:'medium'},
    'Mahindra World City': {apt:[71,95],house:[320,429],villa:[532,713],land:[47,105],trend:'+13.0%',sqft:6200,pincode:'603004',confidence:'high'},
    'Mambakkam': {apt:[57,86],house:[257,389],villa:[428,647],land:[89,145],trend:'+13.0%',sqft:5500,pincode:'600127',confidence:'low'},
    'Manali': {apt:[53,86],house:[240,389],villa:[399,647],land:[89,152],trend:'+13.0%',sqft:5200,pincode:'600068',confidence:'medium'},
    'Manali New Town': {apt:[51,82],house:[229,371],villa:[380,618],land:[82,140],trend:'+13.0%',sqft:5000,pincode:'600103',confidence:'low'},
    'Mangadu': {apt:[57,86],house:[257,389],villa:[428,647],land:[98,159],trend:'+13.0%',sqft:5500,pincode:'600122',confidence:'medium'},
    'Maraimalai Nagar': {apt:[44,70],house:[200,314],villa:[333,523],land:[28,70],trend:'+13.0%',sqft:4200,pincode:'603209',confidence:'medium'},
    'Mathur': {apt:[51,79],house:[229,354],villa:[380,589],land:[82,135],trend:'+13.0%',sqft:4800,pincode:'600068',confidence:'low'},
    'Minjur': {apt:[28,48],house:[126,217],villa:[209,361],land:[21,56],trend:'+13.0%',sqft:2800,pincode:'601203',confidence:'low'},
    'Mogappair': {apt:[95,140],house:[429,629],villa:[713,1046],land:[164,257],trend:'+13.0%',sqft:9000,pincode:'600037',confidence:'medium'},
    'Mogappair West': {apt:[89,133],house:[400,600],villa:[666,998],land:[159,245],trend:'+13.0%',sqft:8500,pincode:'600037',confidence:'medium'},
    'Mudichur': {apt:[53,79],house:[240,354],villa:[399,589],land:[89,140],trend:'+13.0%',sqft:5000,pincode:'600048',confidence:'low'},
    'Nolambur': {apt:[89,127],house:[400,571],villa:[666,951],land:[152,229],trend:'+13.0%',sqft:8200,pincode:'600095',confidence:'low'},
    'Old Washermanpet': {apt:[76,121],house:[343,543],villa:[570,903],land:[135,215],trend:'+13.0%',sqft:7600,pincode:'600021',confidence:'high'},
    'Oragadam': {apt:[44,70],house:[200,314],villa:[333,523],land:[65,112],trend:'+13.0%',sqft:4200,pincode:'602105',confidence:'medium'},
    'Ottiambakkam': {apt:[57,86],house:[257,389],villa:[428,647],land:[89,145],trend:'+13.0%',sqft:5500,pincode:'600130',confidence:'low'},
    'Padappai': {apt:[36,61],house:[160,274],villa:[266,456],land:[35,82],trend:'+13.0%',sqft:3500,pincode:'601301',confidence:'low'},
    'Padi': {apt:[76,114],house:[343,514],villa:[570,856],land:[128,206],trend:'+13.0%',sqft:7200,pincode:'600050',confidence:'low'},
    'Padur': {apt:[70,99],house:[314,446],villa:[523,742],land:[65,98],trend:'+13.0%',sqft:6500,pincode:'603103',confidence:'medium'},
    'Pallavaram': {apt:[76,121],house:[343,543],villa:[570,903],land:[140,234],trend:'+13.0%',sqft:7500,pincode:'600043',confidence:'high'},
    'Pammal': {apt:[63,95],house:[286,429],villa:[475,713],land:[112,175],trend:'+13.0%',sqft:6000,pincode:'600075',confidence:'medium'},
    'Paruthipattu': {apt:[51,76],house:[229,343],villa:[380,570],land:[84,135],trend:'+13.0%',sqft:4800,pincode:'600071',confidence:'low'},
    'Pattabiram': {apt:[48,74],house:[217,331],villa:[361,551],land:[82,131],trend:'+13.0%',sqft:4600,pincode:'600072',confidence:'low'},
    'Periyapalayam': {apt:[20,36],house:[91,160],villa:[152,266],land:[8,33],trend:'+13.0%',sqft:2000,pincode:'601102',confidence:'low'},
    'Perungalathur': {apt:[53,79],house:[240,354],villa:[399,589],land:[89,140],trend:'+13.0%',sqft:5000,pincode:'600063',confidence:'medium'},
    'Ponmar': {apt:[51,76],house:[229,343],villa:[380,570],land:[75,121],trend:'+13.0%',sqft:4800,pincode:'600048',confidence:'low'},
    'Ponneri': {apt:[23,38],house:[103,171],villa:[171,285],land:[14,42],trend:'+13.0%',sqft:2200,pincode:'601204',confidence:'medium'},
    'Poonamallee': {apt:[57,86],house:[257,389],villa:[428,647],land:[105,164],trend:'+13.0%',sqft:5500,pincode:'600056',confidence:'high'},
    'Potheri': {apt:[57,89],house:[257,400],villa:[428,666],land:[82,140],trend:'+13.0%',sqft:5500,pincode:'603203',confidence:'medium'},
    'Puzhal': {apt:[48,74],house:[217,331],villa:[361,551],land:[82,128],trend:'+13.0%',sqft:4600,pincode:'600066',confidence:'low'},
    'Sathangadu': {apt:[48,76],house:[217,343],villa:[361,570],land:[75,128],trend:'+13.0%',sqft:4600,pincode:'600019',confidence:'low'},
    'Selaiyur': {apt:[63,95],house:[286,429],villa:[475,713],land:[105,168],trend:'+13.0%',sqft:6000,pincode:'600073',confidence:'low'},
    'Sembakkam': {apt:[63,95],house:[286,429],villa:[475,713],land:[105,168],trend:'+13.0%',sqft:6000,pincode:'600073',confidence:'low'},
    'Sevvapet': {apt:[19,33],house:[86,149],villa:[143,247],land:[9,33],trend:'+13.0%',sqft:1900,pincode:'602025',confidence:'low'},
    'Singaperumal Koil': {apt:[44,79],house:[200,354],villa:[333,589],land:[28,70],trend:'+13.0%',sqft:4500,pincode:'603204',confidence:'high'},
    'Sriperumbudur': {apt:[44,70],house:[200,314],villa:[333,523],land:[70,117],trend:'+13.0%',sqft:4200,pincode:'602105',confidence:'medium'},
    'Surapet': {apt:[57,89],house:[257,400],villa:[428,666],land:[93,159],trend:'+13.0%',sqft:5500,pincode:'600066',confidence:'low'},
    'Tambaram': {apt:[63,102],house:[286,457],villa:[475,761],land:[105,182],trend:'+13.0%',sqft:6200,pincode:'600045',confidence:'high'},
    'Tambaram West': {apt:[61,91],house:[274,411],villa:[456,685],land:[98,164],trend:'+13.0%',sqft:5800,pincode:'600045',confidence:'medium'},
    'Thalambur': {apt:[74,102],house:[331,457],villa:[551,761],land:[93,135],trend:'+13.0%',sqft:6800,pincode:'600130',confidence:'medium'},
    'Thirumazhisai': {apt:[48,74],house:[217,331],villa:[361,551],land:[75,121],trend:'+13.0%',sqft:4500,pincode:'600124',confidence:'medium'},
    'Thirumudivakkam': {apt:[53,82],house:[240,371],villa:[399,618],land:[89,145],trend:'+13.0%',sqft:5200,pincode:'600132',confidence:'low'},
    'Thirumullaivoyal': {apt:[56,79],house:[254,357],villa:[423,594],land:[105,152],trend:'+13.0%',sqft:5650,pincode:'600062',confidence:'high'},
    'Thiruninravur': {apt:[25,38],house:[114,171],villa:[190,285],land:[42,70],trend:'+13.0%',sqft:2300,pincode:'602024',confidence:'medium'},
    'Thiruporur': {apt:[44,70],house:[200,314],villa:[333,523],land:[51,105],trend:'+13.0%',sqft:4200,pincode:'603110',confidence:'low'},
    'Thiruverkadu': {apt:[57,86],house:[257,389],villa:[428,647],land:[93,145],trend:'+13.0%',sqft:5500,pincode:'600077',confidence:'low'},
    'Tiruvallur Town': {apt:[28,48],house:[126,217],villa:[209,361],land:[13,55],trend:'+13.0%',sqft:2800,pincode:'602001',confidence:'medium'},
    'Tiruvottiyur': {apt:[76,121],house:[343,543],villa:[570,903],land:[128,210],trend:'+13.0%',sqft:7500,pincode:'600019',confidence:'high'},
    'Tollgate': {apt:[76,117],house:[343,526],villa:[570,875],land:[128,210],trend:'+13.0%',sqft:7400,pincode:'600021',confidence:'low'},
    'Tondiarpet': {apt:[89,146],house:[400,657],villa:[666,1093],land:[152,257],trend:'+13.0%',sqft:9200,pincode:'600081',confidence:'high'},
    'Urapakkam': {apt:[48,74],house:[217,331],villa:[361,551],land:[82,128],trend:'+13.0%',sqft:4600,pincode:'603210',confidence:'medium'},
    'Uthukottai': {apt:[18,32],house:[80,143],villa:[133,238],land:[7,30],trend:'+13.0%',sqft:1800,pincode:'602026',confidence:'low'},
    'Vandalur': {apt:[48,74],house:[217,331],villa:[361,551],land:[75,121],trend:'+13.0%',sqft:4500,pincode:'600048',confidence:'medium'},
    'Veppampattu': {apt:[23,37],house:[103,166],villa:[171,276],land:[37,65],trend:'+13.0%',sqft:2200,pincode:'602024',confidence:'low'},
    'Vyasarpadi': {apt:[63,99],house:[286,446],villa:[475,742],land:[105,175],trend:'+13.0%',sqft:6200,pincode:'600039',confidence:'low'},
    'Walajabad': {apt:[20,36],house:[91,160],villa:[152,266],land:[19,51],trend:'+13.0%',sqft:2000,pincode:'631605',confidence:'low'},
    'Wimco Nagar': {apt:[61,91],house:[274,411],villa:[456,685],land:[98,159],trend:'+13.0%',sqft:5800,pincode:'600057',confidence:'low'},
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

    // ── Step 1b: Fuzzy name match — handles typos and minor variants ──
    let bestKey = null, bestSim = 0;
    for (const key of Object.keys(cityDb)) {
      const sim = _strSim(needle, key.toLowerCase());
      if (sim > bestSim) { bestSim = sim; bestKey = key; }
    }
    if (bestKey && bestSim >= 0.72) {
      return { db: cityDb[bestKey], matched: bestKey, source: 'exact' };
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
    if(search.carpetArea){const a=parseInt(search.carpetArea),r=db.sqft,sba=a*1.25;lo=Math.round(sba*r*0.9/1e5);hi=Math.round(sba*r*1.1/1e5);}
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
  // Guard: if backend never responded, attempt a fresh submit now before going to payment
  const valId=sessionStorage.getItem('valuprop_val_id');
  if(!valId){
    try{
      const r=await fetch(`${BACKEND_URL}/api/property/submit`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(search)});
      const d=await r.json();
      if(d.property_id) sessionStorage.setItem('valuprop_prop_id',d.property_id);
      if(d.valuation_id) sessionStorage.setItem('valuprop_val_id',d.valuation_id);
    }catch(e){}
  }
  window.location.href='payment.html';
}
