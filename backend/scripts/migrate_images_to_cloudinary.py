"""Migrar imágenes locales a Cloudinary.

Ejecutar en producción:
  cd /app && python -m scripts.migrate_images_to_cloudinary

Requiere que las env vars de Cloudinary estén configuradas.
"""
import os
import sys
import glob
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import SessionLocal
from models import Product, Banner, ProductImage

LOCAL_PREFIX = "/uploads/images/"
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "uploads", "images")


def upload_to_cloudinary(local_path: str) -> str | None:
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
            api_key=os.getenv("CLOUDINARY_API_KEY", ""),
            api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
        )
        folder = os.getenv("CLOUDINARY_FOLDER", "gracia/products")
        result = cloudinary.uploader.upload(local_path, folder=folder, resource_type="image")
        url = result.get("secure_url") or result.get("url", "")
        return url
    except Exception as e:
        logger.error(f"Error subiendo a Cloudinary: {e}")
        return None


def migrate_local_images():
    db = SessionLocal()
    updated = 0

    # Migrate Product images
    products = db.query(Product).filter(Product.image.like(f"%{LOCAL_PREFIX}%")).all()
    for p in products:
        local_file = p.image.replace(LOCAL_PREFIX, "")
        local_path = os.path.join(UPLOAD_DIR, local_file)
        if not os.path.exists(local_path):
            logger.warning(f"Producto {p.id}: archivo no encontrado {local_path}")
            continue
        url = upload_to_cloudinary(local_path)
        if url:
            p.image = url
            updated += 1
            logger.info(f"Producto {p.id} migrado: {url}")

    # Migrate Banner images
    banners = db.query(Banner).filter(Banner.image_url.like(f"%{LOCAL_PREFIX}%")).all()
    for b in banners:
        local_file = b.image_url.replace(LOCAL_PREFIX, "")
        local_path = os.path.join(UPLOAD_DIR, local_file)
        if not os.path.exists(local_path):
            logger.warning(f"Banner {b.id}: archivo no encontrado {local_path}")
            continue
        url = upload_to_cloudinary(local_path)
        if url:
            b.image_url = url
            updated += 1
            logger.info(f"Banner {b.id} migrado: {url}")

    # Migrate ProductImage records
    images = db.query(ProductImage).filter(ProductImage.url.like(f"%{LOCAL_PREFIX}%")).all()
    for img in images:
        local_file = img.url.replace(LOCAL_PREFIX, "")
        local_path = os.path.join(UPLOAD_DIR, local_file)
        if not os.path.exists(local_path):
            logger.warning(f"ProductImage {img.id}: archivo no encontrado {local_path}")
            continue
        url = upload_to_cloudinary(local_path)
        if url:
            img.url = url
            updated += 1
            logger.info(f"ProductImage {img.id} migrado: {url}")

    db.commit()
    db.close()
    logger.info(f"Migración completada: {updated} imágenes migradas a Cloudinary")
    return updated


if __name__ == "__main__":
    if not os.getenv("CLOUDINARY_CLOUD_NAME"):
        logger.error("CLOUDINARY_CLOUD_NAME no está configurado. Abortando.")
        sys.exit(1)
    migrate_local_images()
