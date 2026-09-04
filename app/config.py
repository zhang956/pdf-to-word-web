import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必须是正整数") from exc
    if value <= 0:
        raise RuntimeError(f"{name} 必须是正整数")
    return value


@dataclass(frozen=True)
class Settings:
    app_password: str
    session_secret: str
    production: bool
    trust_render_proxy: bool
    max_file_size: int
    max_pdf_pages: int
    conversion_workers: int
    max_conversion_jobs: int
    task_ttl_seconds: int
    work_root: Path
    ocr_languages: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        environment = os.environ if env is None else env
        production = environment.get("APP_ENV", "development").lower() == "production"
        password = environment.get("APP_PASSWORD", "")
        secret = environment.get("SESSION_SECRET", "")
        if production and not password:
            raise RuntimeError("生产环境缺少 APP_PASSWORD")
        if production and len(secret) < 32:
            raise RuntimeError("生产环境 SESSION_SECRET 至少需要 32 个字符")

        return cls(
            app_password=password or "local-dev-password",
            session_secret=secret or "local-development-session-secret-only",
            production=production,
            trust_render_proxy=environment.get("TRUST_RENDER_PROXY", "0") == "1",
            max_file_size=_positive_int(environment, "MAX_FILE_SIZE_MB", 30)
            * 1024
            * 1024,
            max_pdf_pages=_positive_int(environment, "MAX_PDF_PAGES", 100),
            conversion_workers=_positive_int(environment, "CONVERSION_WORKERS", 1),
            max_conversion_jobs=_positive_int(environment, "MAX_CONVERSION_JOBS", 2),
            task_ttl_seconds=_positive_int(environment, "TASK_TTL_SECONDS", 3600),
            work_root=Path(environment.get("WORK_ROOT", ".runtime/tasks")),
            ocr_languages=environment.get("OCR_LANGUAGES", "chi_sim+eng"),
        )


settings = Settings.from_env()
MAX_FILE_SIZE = settings.max_file_size
MAX_PDF_PAGES = settings.max_pdf_pages
TASK_TTL_SECONDS = settings.task_ttl_seconds
WORK_ROOT = settings.work_root
OCR_LANGUAGES = settings.ocr_languages
MAX_CONVERSION_JOBS = settings.max_conversion_jobs
