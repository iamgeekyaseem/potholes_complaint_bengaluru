# 🕳 Bengaluru Pothole Reporter — FastAPI Edition

A full-stack Python web app to crowdsource pothole locations across Bengaluru.
**FastAPI** backend handles image processing; the frontend is served as a Jinja2 template.

---

## 📁 Project Structure

```
pothole-reporter/
├── main.py               ← FastAPI app (all routes + logic)
├── templates/
│   └── index.html        ← Jinja2 HTML template (map + UI)
├── static/
│   └── uploads/          ← Local temp dir (not used in prod)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🐍 What Python Does

| Task | Library |
|---|---|
| Web server & API routes | FastAPI + Uvicorn |
| EXIF GPS extraction | piexif + Pillow |
| Adaptive image compression | Pillow (PIL) |
| Supabase Storage upload | supabase-py |
| Database read/write | supabase-py |
| HTML template rendering | Jinja2 |
| Env config | python-dotenv |

---

## 🚀 Setup & Run

### 1. Clone & install
```bash
git clone <your-repo>
cd pothole-reporter

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 3. Run
```bash
uvicorn main:app --reload
# Open http://localhost:8000
```

---

## 🔑 Supabase Setup

1. Create project at [supabase.com](https://supabase.com)
2. Enable **Google Auth**:
   - Google Cloud Console → OAuth 2.0 Client
   - Add credentials to Supabase → Authentication → Providers
3. Run this SQL in Supabase SQL editor:

```sql
-- Table
create table reports (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  user_id uuid references auth.users(id) on delete cascade,
  user_name text,
  image_url text not null,
  latitude double precision not null,
  longitude double precision not null
);

-- RLS
alter table reports enable row level security;

create policy "Public read" on reports for select using (true);
create policy "Auth insert" on reports for insert with check (auth.uid() = user_id);
create policy "Owner delete" on reports for delete using (auth.uid() = user_id);
```

4. Create storage bucket: `pothole-images`

```sql
create policy "Public read images"
  on storage.objects for select using (bucket_id = 'pothole-images');

create policy "Auth upload"
  on storage.objects for insert
  with check (auth.role() = 'authenticated');

create policy "Owner delete images"
  on storage.objects for delete
  using (auth.uid()::text = owner);
```

---

## 🌐 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the HTML app |
| `GET` | `/api/reports` | Fetch all reports |
| `POST` | `/api/reports` | Submit new report (image + coords) |
| `DELETE` | `/api/reports/{id}` | Delete own report |
| `POST` | `/api/extract-gps` | Extract GPS from image (no save) |
| `GET` | `/health` | Health check |

---

## 🖼 Adaptive Compression Logic (Python/Pillow)

| File size | Quality | Max dimension |
|---|---|---|
| > 8 MB | 55% | 1280px |
| > 4 MB | 65% | 1600px |
| > 2 MB | 75% | 1920px |
| ≤ 2 MB | 85% | 1920px |

---

## 🚀 Deploy

### Render (recommended for FastAPI)
1. Push to GitHub
2. New Web Service → Python → `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add env vars from `.env`

### Railway / Fly.io
Same approach — set env vars, deploy via GitHub.

### Add a `Procfile` for Render:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
