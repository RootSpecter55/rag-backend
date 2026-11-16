"""Test configuration. The environment is set before any app module reads settings."""

import os
import tempfile

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5443/rag_test"
)
os.environ.update(
    {
        "APP_ENV": "test",
        "LOG_LEVEL": "WARNING",
        "DATABASE_URL": TEST_DATABASE_URL,
        "ADMIN_API_KEY": "test-admin-key-that-is-at-least-32-characters",
        "STORAGE_PROVIDER": "local",
        "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="rag-test-uploads-"),
        "EMBEDDING_PROVIDER": "fake",
        "LLM_PROVIDER": "fake",
        "DEFAULT_MONTHLY_QUERY_LIMIT": "1000",
    }
)
