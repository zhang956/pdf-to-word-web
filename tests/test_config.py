from pathlib import Path

import pytest

from app.config import Settings


def test_public_defaults_limit_resource_usage():
    settings = Settings.from_env({})

    assert settings.max_file_size == 30 * 1024 * 1024
    assert settings.max_pdf_pages == 100
    assert settings.conversion_workers == 1
    assert settings.max_conversion_jobs == 2
    assert settings.task_ttl_seconds == 3600
    assert settings.work_root == Path(".runtime/tasks")


def test_environment_overrides_numeric_limits():
    settings = Settings.from_env(
        {
            "MAX_FILE_SIZE_MB": "12",
            "MAX_PDF_PAGES": "40",
            "CONVERSION_WORKERS": "2",
            "MAX_CONVERSION_JOBS": "3",
        }
    )

    assert settings.max_file_size == 12 * 1024 * 1024
    assert settings.max_pdf_pages == 40
    assert settings.conversion_workers == 2
    assert settings.max_conversion_jobs == 3


@pytest.mark.parametrize("missing", ["APP_PASSWORD", "SESSION_SECRET"])
def test_production_requires_secrets_without_exposing_values(missing):
    environment = {
        "APP_ENV": "production",
        "APP_PASSWORD": "private-password",
        "SESSION_SECRET": "x" * 32,
    }
    del environment[missing]

    with pytest.raises(RuntimeError, match=missing) as error:
        Settings.from_env(environment)

    assert "private-password" not in str(error.value)


def test_production_rejects_short_session_secret():
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings.from_env(
            {
                "APP_ENV": "production",
                "APP_PASSWORD": "private-password",
                "SESSION_SECRET": "short",
            }
        )
