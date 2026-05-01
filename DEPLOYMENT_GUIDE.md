# ValUprop.in — Deployment Guide

Complete guide: local development → Render.com (free) → AWS production.

---

## Stage 1: Local Development

### Frontend only (no backend needed)
```
# Just open index.html in browser — works completely offline
# Uses static price data and demo payment mode
```

### Full stack locally
```bash
# 1. Set up backend
cd backend
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows

pip install -r requirements.txt

# 2. Install WeasyPrint system deps (for PDF)
# Ubuntu/Debian:
sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1
# macOS:
brew install pango
# Windows: see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html

# 3. Configure environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum

# 4. Create database tables
python init_db.py

# 5. Start backend
uvicorn main:app --reload --port 8000
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs

# 6. Open frontend
# Option A: Open index.html directly in browser
# Option B: VS Code → Live Server extension → index.html → "Open with Live Server"
#           Frontend at http://localhost:5500
```

### Set backend URL in frontend JS
In `js/estimate.js`, `js/results.js`, `js/detail.js` — the first line is:
```js
const BACKEND_URL = window.BACKEND_URL || 'http://localhost:8000';
```
This automatically uses localhost in development. No change needed.

---

## Stage 2: Free Hosting on Render.com

### Prerequisites
- GitHub account
- Render.com account (free)
- All API keys ready (OpenAI, Razorpay, Resend, AWS)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "ValUprop.in initial commit"
git remote add origin https://github.com/yourusername/valuprop
git push -u origin main
```

Add a `.gitignore`:
```
backend/.env
backend/valuprop_dev.db
backend/__pycache__/
backend/*.pyc
*.zip
```

### Step 2 — Deploy on Render
1. Go to https://render.com → New → Blueprint
2. Connect your GitHub repo
3. Render detects `render.yaml` automatically
4. It creates:
   - `valuprop-api` (Python backend)
   - `valuprop-frontend` (static site)
   - `valuprop-db` (PostgreSQL)

### Step 3 — Set environment variables
In Render dashboard → `valuprop-api` → Environment:
```
OPENAI_API_KEY         = sk-proj-...
RAZORPAY_KEY_ID        = rzp_test_...
RAZORPAY_KEY_SECRET    = ...
RESEND_API_KEY         = re_...
AWS_ACCESS_KEY_ID      = ...
AWS_SECRET_ACCESS_KEY  = ...
```

### Step 4 — Update BACKEND_URL in JS
Once deployed, your backend URL will be `https://valuprop-api.onrender.com`.

In each of `js/estimate.js`, `js/results.js`, `js/detail.js`:
```js
// Change this line at the top:
const BACKEND_URL = window.BACKEND_URL || 'https://valuprop-api.onrender.com';
```

Or set it globally in a `<script>` tag in each HTML page before the other scripts:
```html
<script>window.BACKEND_URL = 'https://valuprop-api.onrender.com';</script>
```

### Step 5 — Update Razorpay allowed domains
In Razorpay dashboard → Settings → Website/App → add your Render URL.

### Render free tier limitations
- Backend spins down after 15 minutes of inactivity → ~30s cold start
- PostgreSQL free tier expires after 90 days
- For always-on: upgrade to Starter ($7/month) or migrate to AWS

---

## Stage 3: Production on AWS (when you're ready)

### Architecture (as specified in PRD)
```
Route 53 (DNS)
    ↓
CloudFront (CDN) → S3 (static frontend)
    ↓
API Gateway → Lambda (or EC2 t3.micro)
    ↓
RDS PostgreSQL (db.t3.micro, ap-south-1)
    ↓
S3 (PDF reports)
```

### Step-by-step AWS setup

#### 1. Create S3 bucket for PDFs
```bash
aws s3 mb s3://valuprop-reports --region ap-south-1

# Block all public access
aws s3api put-public-access-block \
  --bucket valuprop-reports \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

#### 2. Create S3 bucket for frontend
```bash
aws s3 mb s3://valuprop-frontend --region ap-south-1
# Enable static website hosting
aws s3 website s3://valuprop-frontend --index-document index.html
# Upload frontend files
aws s3 sync . s3://valuprop-frontend --exclude "backend/*" --exclude "*.zip" --exclude ".git/*"
```

#### 3. Create RDS PostgreSQL
- Engine: PostgreSQL 15
- Instance: db.t3.micro (free tier eligible)
- Storage: 20 GB gp2
- Region: ap-south-1 (Mumbai)
- VPC: default, private subnet
- Enable: automated backups, encryption at rest

Update `DATABASE_URL` in your env:
```
DATABASE_URL=postgresql://valuprop_user:PASSWORD@your-rds.ap-south-1.rds.amazonaws.com:5432/valuprop
```

#### 4. Deploy backend to EC2 (simplest option)
```bash
# t3.micro is free tier eligible
# Ubuntu 22.04 LTS, ap-south-1

# On the instance:
git clone https://github.com/yourusername/valuprop
cd valuprop/backend
pip install -r requirements.txt
sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

# Create systemd service for uvicorn
sudo nano /etc/systemd/system/valuprop.service
```

`/etc/systemd/system/valuprop.service`:
```ini
[Unit]
Description=ValUprop.in API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/valuprop/backend
EnvironmentFile=/home/ubuntu/valuprop/backend/.env
ExecStart=/home/ubuntu/valuprop/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable valuprop
sudo systemctl start valuprop
```

#### 5. Set up Nginx as reverse proxy + SSL
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo nano /etc/nginx/sites-available/valuprop
```

```nginx
server {
    listen 80;
    server_name api.valuprop.in;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

```bash
sudo certbot --nginx -d api.valuprop.in
sudo systemctl reload nginx
```

#### 6. Configure CloudFront for frontend
- Origin: S3 bucket website endpoint
- Custom domain: valuprop.in
- SSL: AWS Certificate Manager (free)
- Price class: India only → lower cost

#### 7. Point domain to CloudFront
In your domain registrar (Namecheap/GoDaddy):
```
valuprop.in     →  CloudFront distribution (CNAME or A record via Route 53)
api.valuprop.in →  EC2 Elastic IP
```

---

## Stage 4: Custom Domain (valuprop.in)

### Namecheap setup (₹800/year for .in)
1. Buy domain at namecheap.com
2. DNS settings:
   ```
   Type  Host    Value
   A     @       <EC2 Elastic IP or CloudFront IP>
   CNAME www     valuprop.in
   CNAME api     <EC2 Elastic IP>
   MX    @       <your email provider>
   ```
3. SSL: Already handled by certbot (Let's Encrypt, free)

### Update ALLOWED_ORIGINS in backend .env
```
ALLOWED_ORIGINS=https://valuprop.in,https://www.valuprop.in
```

### Update BACKEND_URL in frontend JS
```js
const BACKEND_URL = window.BACKEND_URL || 'https://api.valuprop.in';
```

### Add your live Razorpay domain
Razorpay dashboard → Settings → Website/App → add `https://valuprop.in`
Switch from `rzp_test_` keys to `rzp_live_` keys.

---

## Monitoring & Alerts

### Free monitoring setup
```bash
# UptimeRobot (free) — monitors /api/health every 5 minutes
# Alert via email if down
# Sign up at https://uptimerobot.com
# Add monitor: https://api.valuprop.in/api/health
```

### PostHog analytics (free tier)
```html
<!-- Add to index.html <head> -->
<script>
  !function(t,e){/* PostHog snippet */}(window,document)
  posthog.init('YOUR_POSTHOG_KEY', {api_host: 'https://app.posthog.com'})
</script>
```

### Log key funnel events in JS
```js
// In estimate.js after form submit:
posthog.capture('form_submitted', { city, locality, type: selectedType })

// In results.js after estimate shown:
posthog.capture('estimate_viewed', { value_range: `${lo}–${hi}` })

// In payment.js after success:
posthog.capture('payment_success', { amount: 99 })
```

---

## Cost Estimate (at 100 paid reports/month)

| Service          | Cost/month |
|-----------------|-----------|
| EC2 t3.micro    | ₹600 (or free tier) |
| RDS db.t3.micro | ₹1,200    |
| S3 (reports)    | ₹50       |
| CloudFront CDN  | ₹100      |
| OpenAI API      | ₹800 (~100 free + 100 paid × ₹4) |
| Resend email    | Free (3k/month) |
| Domain (.in)    | ₹70 (₹800/year) |
| **Total**       | **~₹2,820/month** |
| Revenue (100×₹99) | **₹9,900/month** |
| **Net margin**  | **₹7,080/month** |

At 500 paid reports/month, revenue is ₹49,500 vs ~₹5,000 costs.
