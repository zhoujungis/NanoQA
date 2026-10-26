"""附件存储抽象（§53）：v0.1 本地文件，S3/R2 留桩，接口形状不变。"""
import uuid
from pathlib import Path

from django.conf import settings


class StorageBackend:
    def save(self, file_obj, filename: str) -> str:  # 返回 storage_key
        raise NotImplementedError

    def open(self, storage_key: str):
        raise NotImplementedError

    def delete(self, storage_key: str):
        raise NotImplementedError

    def path(self, storage_key: str) -> Path:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.MEDIA_ROOT) / "attachments"
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"{uuid.uuid4().hex}{suffix}"

    def save(self, file_obj, filename: str) -> str:
        key = self._key(filename)
        target = self.root / key
        with open(target, "wb") as out:
            for chunk in file_obj.chunks():
                out.write(chunk)
        return key

    def open(self, storage_key: str):
        return open(self.path(storage_key), "rb")

    def delete(self, storage_key: str):
        target = self.path(storage_key)
        if target.exists():
            target.unlink()

    def path(self, storage_key: str) -> Path:
        # 防目录穿越
        target = (self.root / storage_key).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise ValueError("invalid storage key")
        return target


class S3StorageBackend(StorageBackend):  # pragma: no cover - v0.2 对象存储桩
    """Cloudflare R2 / S3 presigned 上传桩：实现形状与 Local 一致。"""

    def save(self, file_obj, filename: str) -> str:
        raise NotImplementedError("对象存储未配置，v0.2 启用")

    def open(self, storage_key: str):
        raise NotImplementedError("对象存储未配置，v0.2 启用")

    def delete(self, storage_key: str):
        raise NotImplementedError("对象存储未配置，v0.2 启用")

    def path(self, storage_key: str) -> Path:
        raise NotImplementedError("对象存储未配置，v0.2 启用")


def get_storage() -> StorageBackend:
    return LocalStorageBackend()
