import os
import io
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from PIL import Image
import piexif
from supabase import create_client, Client
from dotenv import load_dotenv

# ─── CONFIG ───────────────────────────────────────────────────────────────────
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET = "pothole-images"
UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── SUPABASE CLIENT ──────────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY)

# ─── FASTAPI APP ──────────────────────────────────────────────────────────────
app = FastAPI(title="Bengaluru Pothole Reporter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def extract_gps_from_exif(image_bytes: bytes) -> Optional[dict]:
    """Extract GPS coordinates from image EXIF data."""
    try:
        exif_data = piexif.load(image_bytes)
        gps = exif_data.get("GPS", {})
        if not gps:
            return None

        def to_degrees(value):
            d, m, s = value
            return d[0]/d[1] + m[0]/m[1]/60 + s[0]/s[1]/3600

        lat_raw = gps.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        lon_raw = gps.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)

        if not (lat_raw and lon_raw):
            return None

        lat = to_degrees(lat_raw)
        lon = to_degrees(lon_raw)

        if lat_ref and lat_ref.decode() == "S":
            lat = -lat
        if lon_ref and lon_ref.decode() == "W":
            lon = -lon

        return {"lat": round(lat, 7), "lng": round(lon, 7)}
    except Exception:
        return None


def compress_image_adaptive(image_bytes: bytes) -> bytes:
    """Adaptively compress image based on size."""
    size_mb = len(image_bytes) / (1024 * 1024)

    if size_mb > 8:
        quality, max_dim = 55, 1280
    elif size_mb > 4:
        quality, max_dim = 65, 1600
    elif size_mb > 2:
        quality, max_dim = 75, 1920
    else:
        quality, max_dim = 85, 1920

    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA → RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if needed
    w, h = img.size
    if w > max_dim or h > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def upload_to_supabase(file_bytes: bytes, user_id: str) -> str:
    """Upload compressed image to Supabase Storage, return public URL."""
    filename = f"{user_id}/{uuid.uuid4().hex}.jpg"
    supabase.storage.from_(BUCKET).upload(
        path=filename,
        file=file_bytes,
        file_options={"content-type": "image/jpeg", "upsert": "false"},
    )
    res = supabase.storage.from_(BUCKET).get_public_url(filename)
    return res


def get_current_user(request: Request) -> Optional[dict]:
    """Extract user from session token in cookie."""
    token = request.cookies.get("sb-access-token")
    if not token:
        return None
    try:
        user = supabase.auth.get_user(token)
        return user.user if user else None
    except Exception:
        return None


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    })


@app.get("/api/reports")
async def get_reports():
    """Fetch all pothole reports."""
    try:
        res = supabase.table("reports").select("*").order("created_at", desc=True).execute()
        return JSONResponse(content={"reports": res.data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reports")
async def create_report(
    request: Request,
    image: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    user_id: str = Form(...),
    user_name: str = Form(...),
):
    """
    Create a new pothole report.
    - Reads EXIF from uploaded image
    - Falls back to manually provided lat/lng
    - Compresses image adaptively
    - Uploads to Supabase Storage
    - Saves record to DB
    """
    image_bytes = await image.read()

    # 1. Try EXIF GPS
    gps = extract_gps_from_exif(image_bytes)

    # 2. Fall back to manual coordinates
    if not gps:
        if latitude is None or longitude is None:
            raise HTTPException(
                status_code=422,
                detail="No GPS found in image. Please provide latitude and longitude manually."
            )
        gps = {"lat": latitude, "lng": longitude}

    # 3. Compress
    compressed = compress_image_adaptive(image_bytes)
    original_kb = len(image_bytes) // 1024
    compressed_kb = len(compressed) // 1024

    # 4. Upload to Supabase Storage
    try:
        image_url = upload_to_supabase(compressed, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    # 5. Insert into DB
    try:
        record = {
            "user_id": user_id,
            "user_name": user_name,
            "image_url": image_url,
            "latitude": gps["lat"],
            "longitude": gps["lng"],
        }
        res = supabase.table("reports").insert(record).execute()
        report = res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

    return JSONResponse(content={
        "report": report,
        "gps_source": "exif" if not (latitude or longitude) else "manual",
        "compression": {
            "original_kb": original_kb,
            "compressed_kb": compressed_kb,
            "ratio": round(original_kb / max(compressed_kb, 1), 2),
        },
    })


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str, user_id: str, image_url: str):
    """Delete a report (owner only, enforced by RLS + manual check)."""
    try:
        # Verify ownership via DB
        existing = supabase.table("reports").select("user_id, image_url").eq("id", report_id).single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Report not found")
        if existing.data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not your report")

        # Delete from storage
        url_path = existing.data["image_url"]
        path_part = url_path.split(f"/object/public/{BUCKET}/")[-1]
        supabase.storage.from_(BUCKET).remove([path_part])

        # Delete from DB
        supabase.table("reports").delete().eq("id", report_id).execute()
        return JSONResponse(content={"deleted": report_id})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract-gps")
async def extract_gps(image: UploadFile = File(...)):
    """Extract GPS from uploaded image EXIF without saving anything."""
    image_bytes = await image.read()
    gps = extract_gps_from_exif(image_bytes)
    if gps:
        return JSONResponse(content={"found": True, **gps})
    return JSONResponse(content={"found": False})


# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
