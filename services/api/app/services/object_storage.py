"""Object storage abstraction for clip uploads."""
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO, Protocol

import structlog

logger = structlog.get_logger(__name__)


class ObjectStorage(Protocol):
    """Minimal interface for upload storage."""

    async def put(self, key: str, data: BinaryIO, content_type: str = "video/mp4") -> str:
        """Store object. Returns the storage reference (key or URL)."""
        ...

    async def get_path(self, key: str) -> str:
        """Return a local file path for the object (download if needed)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete the object."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if the object exists."""
        ...

    async def size(self, key: str) -> int | None:
        """Return the object size in bytes, or None if it does not exist."""
        ...


class LocalStorage:
    """Local filesystem storage (dev/testing)."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: BinaryIO, content_type: str = "video/mp4") -> str:
        del content_type
        dest = self._base / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            while True:
                chunk = data.read(4 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        logger.info("local_storage_put key=%s path=%s", key, dest)
        return str(dest.resolve())

    async def get_path(self, key: str) -> str:
        p = self._base / key
        if not p.is_file():
            raise FileNotFoundError(f"Local file missing: {key}")
        return str(p.resolve())

    async def delete(self, key: str) -> None:
        p = self._base / key
        try:
            if p.is_file():
                p.unlink()
                logger.info("local_storage_delete key=%s", key)
        except OSError:
            logger.warning("local_storage_delete_failed key=%s", key, exc_info=True)
            raise

    async def exists(self, key: str) -> bool:
        return (self._base / key).is_file()

    async def size(self, key: str) -> int | None:
        p = self._base / key
        if not p.is_file():
            return None
        return p.stat().st_size


class S3Storage:
    """S3-compatible storage (Cloudflare R2, AWS S3, MinIO)."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        temp_dir: str | Path = "/tmp/onflow-downloads",
    ) -> None:
        import boto3

        self._bucket = bucket
        self._temp = Path(temp_dir)
        self._temp.mkdir(parents=True, exist_ok=True)
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def put(self, key: str, data: BinaryIO, content_type: str = "video/mp4") -> str:
        import asyncio

        def _upload():
            self._s3.upload_fileobj(
                data,
                self._bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )

        await asyncio.to_thread(_upload)
        logger.info("s3_storage_put bucket=%s key=%s", self._bucket, key)
        return f"s3://{self._bucket}/{key}"

    async def get_path(self, key: str) -> str:
        import asyncio

        local = self._temp / key.replace("/", "_")
        if local.is_file():
            return str(local)

        def _download():
            local.parent.mkdir(parents=True, exist_ok=True)
            self._s3.download_file(self._bucket, key, str(local))

        await asyncio.to_thread(_download)
        return str(local)

    async def delete(self, key: str) -> None:
        import asyncio

        def _del():
            self._s3.delete_object(Bucket=self._bucket, Key=key)

        try:
            await asyncio.to_thread(_del)
            logger.info("s3_storage_delete bucket=%s key=%s", self._bucket, key)
        except Exception:
            logger.warning("s3_storage_delete_failed key=%s", key, exc_info=True)
            raise

        local = self._temp / key.replace("/", "_")
        try:
            if local.is_file():
                local.unlink()
        except OSError:
            pass

    async def exists(self, key: str) -> bool:
        import asyncio

        def _head():
            try:
                self._s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_head)

    async def size(self, key: str) -> int | None:
        import asyncio

        def _head() -> int | None:
            try:
                resp = self._s3.head_object(Bucket=self._bucket, Key=key)
                return int(resp.get("ContentLength", 0))
            except Exception:
                return None

        return await asyncio.to_thread(_head)


def build_storage() -> ObjectStorage:
    """Factory: returns S3Storage if configured, else LocalStorage."""
    from app.core.config import get_settings

    settings = get_settings()
    bucket = os.environ.get("ONFLOW_S3_BUCKET", "").strip()
    endpoint = os.environ.get("ONFLOW_S3_ENDPOINT", "").strip()
    access = os.environ.get("ONFLOW_S3_ACCESS_KEY", "").strip()
    secret = os.environ.get("ONFLOW_S3_SECRET_KEY", "").strip()

    if bucket and endpoint and access and secret:
        logger.info("Using S3 storage bucket=%s endpoint=%s", bucket, endpoint)
        return S3Storage(
            bucket=bucket,
            endpoint_url=endpoint,
            access_key=access,
            secret_key=secret,
        )

    logger.info("Using local storage dir=%s", settings.upload_dir)
    return LocalStorage(settings.upload_dir)
