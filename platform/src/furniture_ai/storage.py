import io
import os
import re
import subprocess
import sys
import warnings

import boto3
from botocore.config import Config
from PIL import Image, ImageOps, UnidentifiedImageError

from furniture_ai.errors import DomainError


class Storage:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.data_dir.resolve()
        self.s3 = None
        if settings.storage_backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            self.s3 = boto3.client(
                "s3",
                region_name=settings.s3_region,
                endpoint_url=settings.s3_endpoint,
                config=Config(
                    connect_timeout=5, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}
                ),
            )

    @staticmethod
    def key(key: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9_./-]{1,250}", key) or key.startswith("/"):
            raise ValueError("Invalid object key")
        if any(p in {".", "..", ""} for p in key.split("/")):
            raise ValueError("Invalid object key")
        return key

    def put(self, key: str, data: bytes, content_type: str):
        key = self.key(key)
        if self.s3:
            kwargs = {"ServerSideEncryption": "AES256"}
            if self.settings.s3_kms_key:
                kwargs = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self.settings.s3_kms_key}
            self.s3.put_object(
                Bucket=self.settings.s3_bucket, Key=key, Body=data, ContentType=content_type, **kwargs
            )
        else:
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            import tempfile

            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                temp = f.name
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, path)

    def get(self, key: str) -> bytes:
        key = self.key(key)
        if self.s3:
            response = self.s3.get_object(Bucket=self.settings.s3_bucket, Key=key)
            with response["Body"] as body:
                return body.read(30 * 1024 * 1024)
        return (self.root / key).read_bytes()

    def delete(self, key: str):
        key = self.key(key)
        if self.s3:
            self.s3.delete_object(Bucket=self.settings.s3_bucket, Key=key)
        else:
            (self.root / key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str):
        prefix = self.key(prefix).rstrip("/") + "/"
        if self.s3:
            for page in self.s3.get_paginator("list_objects_v2").paginate(
                Bucket=self.settings.s3_bucket, Prefix=prefix
            ):
                objects = [{"Key": x["Key"]} for x in page.get("Contents", [])]
                if objects:
                    result = self.s3.delete_objects(
                        Bucket=self.settings.s3_bucket, Delete={"Objects": objects, "Quiet": True}
                    )
                    if result.get("Errors"):
                        raise RuntimeError("Some storage deletions failed")
        else:
            import shutil

            shutil.rmtree(self.root / prefix, ignore_errors=False) if (self.root / prefix).exists() else None


def sanitize_image(raw: bytes, settings, kind: str = "photo", page: int = 0):
    if not raw or len(raw) > settings.max_upload_bytes:
        raise DomainError("UPLOAD_SIZE", "File is empty or larger than the upload limit.", 413)
    if raw.startswith(b"%PDF-"):
        if kind != "floor_plan":
            raise DomainError("FILE_TYPE", "PDF files are accepted only as floor plans.")
        try:
            child = subprocess.run(
                [sys.executable, "-m", "furniture_ai.rasterize", str(page)],
                input=raw,
                capture_output=True,
                timeout=20,
                check=True,
            )
            raw = child.stdout
        except (subprocess.SubprocessError, OSError) as e:
            raise DomainError("INVALID_PDF", "Cannot render this PDF page within the file limits.") from e
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in {"JPEG", "PNG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Only single-frame JPEG, PNG or WebP")
            if image.width * image.height > settings.max_pixels or min(image.size) < 32:
                raise ValueError("Image dimensions outside limits")
            image.load()
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
            if kind == "mask":
                image = image.convert("L").point(lambda x: 255 if x >= 128 else 0)
                fmt, mime = "PNG", "image/png"
            else:
                rgba = image.convert("RGBA")
                image = Image.new("RGB", rgba.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
                fmt, mime = "JPEG", "image/jpeg"
            output = io.BytesIO()
            image.save(output, format=fmt, quality=92)
            return output.getvalue(), image.width, image.height, mime
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as e:
        raise DomainError(
            "INVALID_IMAGE", "Upload a valid, single-frame image within the pixel limit."
        ) from e
