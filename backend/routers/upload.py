import os, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from auth import require_admin

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("")
def upload_image(file: UploadFile = File(...), admin=Depends(require_admin)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Formato no válido. Usa: jpg, png, webp, gif")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    url = f"/uploads/images/{filename}"
    return {"url": url, "filename": filename}
