from app.core.config import Settings
from app.providers.storage.base import StorageProvider
from app.providers.storage.local import LocalDiskStorage
from app.providers.storage.s3 import S3Storage


# Factory: picks the storage implementation from config; the rest of the app sees the interface.
def create_storage(settings: Settings) -> StorageProvider:
    if settings.storage_provider == "s3":
        # Presence of bucket and region is checked by Settings validation.
        return S3Storage(settings.s3_bucket or "", settings.aws_region or "")
    return LocalDiskStorage(settings.local_storage_dir)
