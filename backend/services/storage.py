"""Almacenamiento de imágenes con backends intercambiables.

- `local` (default): guarda en disco (backend/uploads/images). En Render free el
  disco es efímero: configurá cloudinary o s3 en producción para no perder imágenes.
- `cloudinary`: requiere CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY y CLOUDINARY_API_SECRET.
- `s3`: requiere AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET, AWS_REGION.

STORE = os.getenv("STORAGE_BACKEND", "local")
"""
import os
import uuid
import logging

logger = logging.getLogger("gracia.storage")

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "uploads", "images"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_local(data: bytes, ext: str) -> str:
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    logger.info(f"Imagen guardada en disco: {filename}")
    return f"/uploads/images/{filename}"


def _save_cloudinary(data: bytes, ext: str) -> str:
    import cloudinary
    import cloudinary.uploader
    from cloudinary import api

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
        api_key=os.getenv("CLOUDINARY_API_KEY", ""),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    )
    folder = os.getenv("CLOUDINARY_FOLDER", "gracia/products")
    result = cloudinary.uploader.upload(data, folder=folder, resource_type="image")
    url = result.get("secure_url") or result.get("url", "")
    if not url:
        raise RuntimeError("Cloudinary no devolvió una URL")
    logger.info(f"Imagen subida a Cloudinary: {url}")
    return url


def _save_s3(data: bytes, ext: str) -> str:
    import boto3

    bucket = os.getenv("AWS_BUCKET", "")
    region = os.getenv("AWS_REGION", "us-east-1")
    if not bucket:
        raise RuntimeError("AWS_BUCKET no está configurado para STORAGE_BACKEND=s3")

    key = f"products/{uuid.uuid4().hex}.{ext}"
    client = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    )
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=f"image/{ext}")
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    logger.info(f"Imagen subida a S3: {url}")
    return url


def save_image(data: bytes, ext: str) -> str:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    try:
        if backend == "cloudinary":
            return _save_cloudinary(data, ext)
        if backend == "s3":
            return _save_s3(data, ext)
        return _save_local(data, ext)
    except Exception as e:
        logger.error(f"Fallo al guardar imagen en backend '{backend}': {e}")
        raise
