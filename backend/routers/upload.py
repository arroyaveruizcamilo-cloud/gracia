import os, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from auth import require_admin

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB

# Magic bytes detection (no confiar en el Content-Type del cliente)
MAGIC_BYTES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"RIFF": "webp",
}


def detect_extension(data: bytes) -> str | None:
    for magic, ext in MAGIC_BYTES.items():
        if data.startswith(magic):
            return ext
    if data[8:12] == b"WEBP" and data.startswith(b"RIFF"):
        return "webp"
    return None


@router.post("")
def upload_image(file: UploadFile = File(...), admin=Depends(require_admin)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Formato no válido. Usa: jpg, png, webp, gif")

    data = file.file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="La imagen supera el máximo de 5MB")

    ext = detect_extension(data)
    if ext is None:
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida")

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(data)

    url = f"/uploads/images/{filename}"
    return {"url": url, "filename": filename}
