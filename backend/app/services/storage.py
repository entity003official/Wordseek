from __future__ import annotations

import io
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from minio import Minio

from ..core.config import settings


class ObjectStorage:
    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, object_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, object_key: str) -> None:
        raise NotImplementedError

    def presigned_get(self, object_key: str, expires_minutes: int = 5) -> str | None:
        return None

    def healthcheck(self) -> bool:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        self.root = settings.data_dir / "audio_v1"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        path = (self.root / object_key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("非法对象路径")
        return path

    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, object_key: str) -> bytes:
        return self._path(object_key).read_bytes()

    def delete(self, object_key: str) -> None:
        self._path(object_key).unlink(missing_ok=True)

    def healthcheck(self) -> bool:
        return self.root.is_dir()


class MinioObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(self.bucket, object_key, io.BytesIO(content), len(content), content_type=content_type)

    def get(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)

    def presigned_get(self, object_key: str, expires_minutes: int = 5) -> str:
        return self.client.presigned_get_object(self.bucket, object_key, expires=timedelta(minutes=expires_minutes))

    def healthcheck(self) -> bool:
        return self.client.bucket_exists(self.bucket)


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    return MinioObjectStorage() if settings.storage_backend == "minio" else LocalObjectStorage()
