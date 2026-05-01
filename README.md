# NestValue — Property Price Estimator

A website for estimating apartment and house prices in Chennai & Bangalore,
sourcing data from MagicBricks, 99acres, Housing.com, and NoBroker.

---

## Project Structure

```
nestvalue/
├── index.html          ← Home / search form
├── loading.html        ← Loading screen (animated)
├── results.html        ← Free summary + paywall
├── payment.html        ← ₹100 Razorpay payment
├── detail.html         ← Detailed report (post-payment)
├── css/
│   └── style.css       ← All styles
├── js/
│   ├── app.js          ← Shared data + utilities
│   ├── results.js      ← Results page logic
│   ├── payment.js      ← Razorpay integration
│   └── detail.js       ← Detailed report rendering
├── backend/
│   ├── main.py         ← FastAPI backend (Python)
│   └── requirements.txt
└── README.md
```

---

## STEP 1: Run locally (no backend needed)

The frontend works fully without a backend (uses built-in price data).

### Option A: Open directly in browser
Just double-click `index.html` — it works as a static site.

### Option B: Use VS Code Live Server (recommended)
1. Install VS Code: https://code.visualstudio.com
2. Install the "Live Server" extension
3. Right-click `index.html` → "Open with Live Server"
4. Opens at http://localhost:5500

---

## STEP 2: Set up Razorpay (for real payments)

1. Sign up free at https://razorpay.com
2. Go to Settings → API Keys → Generate Test Key
3. Copy your **Key ID** (starts with `rzp_test_...`)
4. Open `js/payment.js` and replace:
   ```js
   const RAZORPAY_KEY_ID = 'YOUR_RAZORPAY_KEY_ID';
   ```
   with your actual key.

**Testing payments:** Use Razorpay's test card:
- Card: 4111 1111 1111 1111
- Expiry: Any future date
- CVV: Any 3 digits
- OTP: 1234

---

## STEP 3: Run the Python backend (for live scraping)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate     # Mac/Linux
venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Create .env file
echo "RAZORPAY_KEY_ID=rzp_test_YOUR_KEY" > .env
echo "RAZORPAY_KEY_SECRET=YOUR_SECRET" >> .env

# Start the server
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

---

## STEP 4: Deploy free (Render.com)

### Frontend
1. Create account at https://netlify.com
2. Drag and drop your `nestvalue/` folder (without `backend/`)
3. Your site is live at: `https://your-site.netlify.app`

### Backend
1. Create account at https://render.com
2. Connect your GitHub repo
3. New → Web Service → select your repo
4. Build command: `pip install -r backend/requirements.txt`
5. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables in Render dashboard:
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`

---

## STEP 5: Move to your own domain

1. Buy a domain at https://namecheap.com (~₹800/year for .in)
2. In Netlify: Site Settings → Domain Management → Add Custom Domain
3. In Namecheap: Point DNS to Netlify's nameservers
4. SSL certificate is auto-provisioned (free)

---

## Payment Flow

```
User clicks "Unlock Full Report for ₹100"
    ↓
payment.html loads
    ↓
User clicks "Pay ₹100 Securely"
    ↓
Razorpay popup opens (UPI / Card / NetBanking)
    ↓
User pays
    ↓
payment.js receives success callback
    ↓
markPaid() saves session flag
    ↓
Redirect to detail.html
    ↓
detail.js checks isPaid() → shows full report
```

---

## Adding More Cities

In `js/app.js`, add to `PRICE_DATA`:
```js
"Mumbai": {
  "Bandra": { "2 BHK": { min: 200, max: 350, avg: 265, ... } }
}
```

In `index.html`, add a city pill:
```html
<div class="city-pill" data-city="Mumbai" onclick="selectCity(this)">Mumbai</div>
```

---

## Support

For questions, email: support@nestvalue.in
