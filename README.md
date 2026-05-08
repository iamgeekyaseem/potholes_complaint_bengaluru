# 🕳️ Bengaluru Pothole Reporter

A full-stack civic web app to crowdsource and map pothole locations across Bengaluru. Built with **FastAPI** + **Supabase** + **Leaflet.js**.

🌐 **Live Demo:** [potholes-complaint-bengaluru.onrender.com](https://potholes-complaint-bengaluru.onrender.com)

---

## ✨ Features

- 📸 **Photo upload** with automatic GPS extraction from EXIF metadata
- 🗺️ **Interactive Leaflet map** showing all reported potholes
- 📍 **Draggable marker** for manual location setting when GPS is missing
- 🔐 **Google OAuth** login via Supabase Auth
- 🖼️ **Adaptive image compression** using Python Pillow (4-tier quality scaling)
- 🗑️ **Delete your own reports** — enforced via Supabase RLS
- 🌙 **Dark / Light map toggle** (OpenStreetMap ↔ CartoDB Dark)
- 📊 **Live report stats** — total count and today's reports
- 🔒 **Row Level Security** — users can only delete their own data
- 📱 **Mobile-first responsive UI**

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | HTML + Tailwind CSS + Vanilla JS |
| Map | Leaflet.js + OpenStreetMap |
| Database | Supabase (PostgreSQL) |
| Storage | Supabase Storage |
| Auth | Supabase Auth + Google OAuth |
| Image processing | Pillow + piexif |
| Deployment | Render.com |

---

## 📁 Project Structure

```
pothole-reporter/
├── main.py                 ← FastAPI app (all routes + Python logic)
├── templates/
│   └── index.html          ← Frontend (map, UI, Supabase JS client)
├── static/
│   └── uploads/            ← Temp directory (not used in production)
├── requirements.txt
├── .env                    ← Your credentials (never commit this)
├── .env.example            ← Template for environment variables
├── .gitignore
└── README.md
```

---

## 🚀 Local Development

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/pothole-reporter.git
cd pothole-reporter
```

### 2. Create and activate virtual environment
```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
```

### 5. Run the server
```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000)

> **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🗃️ Supabase Setup

### Database Table
```sql
create table reports (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  user_id uuid references auth.users(id) on delete cascade,
  user_name text,
  image_url text not null,
  latitude double precision not null,
  longitude double precision not null
);
```

### Row Level Security
```sql
alter table reports enable row level security;

create policy "Public read"
  on reports for select using (true);

create policy "Auth insert"
  on reports for insert
  with check (auth.uid() = user_id);

create policy "Owner delete"
  on reports for delete
  using (auth.uid() = user_id);
```

### Storage Bucket
Create a bucket named `pothole-images` with these policies:

```sql
-- Public read
create policy "Public read images"
  on storage.objects for select
  using (bucket_id = 'pothole-images');

-- Authenticated upload
create policy "Auth upload"
  on storage.objects for insert
  with check (auth.role() = 'authenticated');

-- Owner delete
create policy "Owner delete images"
  on storage.objects for delete
  using (auth.uid() = owner::uuid);
```

---

## 🔑 Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com) → Create a new project
2. APIs & Services → OAuth consent screen → External → fill in app name
3. APIs & Services → Credentials → Create OAuth Client ID → Web application
4. Add to **Authorized JavaScript origins:**
   ```
   http://localhost:8000
   https://your-app.onrender.com
   ```
5. Add to **Authorized redirect URIs:**
   ```
   https://your-project.supabase.co/auth/v1/callback
   ```
6. Copy **Client ID** and **Client Secret** → paste into Supabase → Authentication → Providers → Google

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the HTML app |
| `GET` | `/api/reports` | Fetch all pothole reports |
| `POST` | `/api/reports` | Submit a new report |
| `DELETE` | `/api/reports/{id}` | Delete own report |
| `POST` | `/api/extract-gps` | Extract GPS from image (no save) |
| `GET` | `/health` | Health check |

---

## 🖼️ Adaptive Image Compression

Python Pillow compresses images server-side before uploading to Supabase Storage:

| File size | Quality | Max dimension |
|---|---|---|
| > 8 MB | 55% | 1280px |
| > 4 MB | 65% | 1600px |
| > 2 MB | 75% | 1920px |
| ≤ 2 MB | 85% | 1920px |

---

## ☁️ Deployment (Render)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect repo
3. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
4. Add environment variables (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY)
5. Click **Create Web Service**
6. Update Supabase → Auth → URL Configuration with your Render URL

---

## 🔮 Future Improvements

- [ ] Severity tagging (low / medium / high)
- [ ] Upvotes and validation by other users
- [ ] Heatmap visualization
- [ ] Offline upload queue (PWA)
- [ ] Admin dashboard for BBMP authorities
- [ ] Email notifications when a report is resolved

---

## ⚠️ Privacy

- Your photo's GPS location is **publicly visible** on the map
- Avoid uploading photos with **faces** or **license plates**
- EXIF location data is extracted server-side and stored in the database

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

Made with ❤️ for Bengaluru 🇮🇳