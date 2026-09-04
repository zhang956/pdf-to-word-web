# Render Public Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Secure the existing PDF-to-Word web app with a shared password and deploy it from GitHub to a free Render HTTPS endpoint.

**Architecture:** Keep the existing single-process FastAPI and in-memory task model, add focused configuration/auth/rate-limit boundaries, and package the application as a non-root Docker service. GitHub contains only source and deployment descriptors; Render injects all secrets and supplies the ephemeral runtime.

**Tech Stack:** Python 3.12, FastAPI/Starlette sessions, Uvicorn, PyMuPDF, python-docx, Tesseract OCR, Docker, Render Blueprint, GitHub.

**Spec:** `docs/superpowers/specs/2026-09-04-render-public-deployment-design.md`

## Global Constraints

- Render free Web Service with the platform `onrender.com` HTTPS address.
- `APP_PASSWORD` and `SESSION_SECRET` exist only as environment variables; no secret may enter source, logs, Git, Docker context, or documentation examples.
- `说明.txt`, `.env`, `.runtime`, `.venv`, upload files, and output files must be ignored.
- Public defaults are 30 MB, 100 pages, one worker thread, and two total conversion slots.
- Production uses secure `HttpOnly`, `SameSite=Lax` signed session cookies.
- The service listens on `0.0.0.0:$PORT`, runs as a non-root container user, and exposes public `/health`.
- Work proceeds test-first; existing conversion regression tests must remain green.

---

### Task 1: Environment Configuration and Secret-Safe Ignore Rules

**Files:**
- Modify: `.gitignore`
- Modify: `app/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.from_env(env: Mapping[str, str] | None = None) -> Settings` with `app_password`, `session_secret`, `production`, `max_file_size`, `max_pdf_pages`, `conversion_workers`, `max_conversion_jobs`, `task_ttl_seconds`, and `work_root`.
- Produces: `settings`, the validated runtime configuration consumed by later tasks.

- [ ] **Step 1: Write failing tests** for production secret validation, local injected secrets, numeric environment overrides, and exact 30 MB/100 page/1 worker/2 slot defaults.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_config.py -v` and confirm failures identify missing `Settings` behavior.
- [ ] **Step 3: Implement `Settings`** with explicit environment parsing and errors that name missing variables without showing their values; keep compatibility constants only where existing modules still require them.
- [ ] **Step 4: Add ignore rules** for `说明.txt`, `.env`, `.env.*`, `*.pem`, `*.key`, `.runtime/`, `.venv/`, and caches; verify with `git check-ignore` after repository initialization.
- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_config.py tests/test_validation.py -v` and confirm all pass.

### Task 2: Password Authentication, Session Protection, and Health Check

**Files:**
- Create: `app/auth.py`
- Modify: `app/main.py`
- Create: `app/static/login.html`
- Modify: `requirements.txt`
- Create: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Settings` and `settings` from Task 1.
- Produces: `is_authenticated(request: Request) -> bool`, `require_api_auth(request: Request) -> None`, `validate_same_origin(request: Request) -> None`, `/login`, `/logout`, and `/health`.

- [ ] **Step 1: Write failing auth tests** covering public health, home redirect, API 401 JSON, correct/incorrect password, logout, no password in session data, cookie flags, and cross-origin POST rejection.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_auth.py -v` and confirm the new routes and protection do not exist.
- [ ] **Step 3: Add `itsdangerous` dependency** and implement constant-time password comparison plus same-origin validation in `app/auth.py`.
- [ ] **Step 4: Add `SessionMiddleware` and routes** in `app/main.py`; protect home and every conversion/task endpoint while leaving static assets, login, and health public.
- [ ] **Step 5: Create the Chinese login page** with a password field, generic error copy, and no secret-bearing client storage.
- [ ] **Step 6: Run** `.venv/bin/python -m pytest tests/test_auth.py tests/test_api.py tests/test_web.py -v` and adapt existing API fixtures to log in without weakening production behavior.

### Task 3: Public Resource Limits

**Files:**
- Create: `app/rate_limit.py`
- Modify: `app/main.py`
- Modify: `app/converter.py`
- Modify: `app/errors.py`
- Create: `tests/test_rate_limit.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_converter.py`

**Interfaces:**
- Consumes: `settings.max_pdf_pages`, `settings.conversion_workers`, and `settings.max_conversion_jobs`.
- Produces: `SlidingWindowLimiter.check(key: str, now: float | None = None) -> bool` and `convert_pdf(..., max_pages: int = settings.max_pdf_pages) -> None`.

- [ ] **Step 1: Write failing tests** for ten login attempts per ten minutes, five conversion submissions per ten minutes, independent IP buckets, window expiry, third-task 503, and a PDF exceeding the page limit.
- [ ] **Step 2: Run** the focused new tests and confirm failures represent absent limiting behavior.
- [ ] **Step 3: Implement the in-memory limiter** using a lock, monotonic timestamps, bounded pruning, direct client IP by default, and Render's trusted proxy header only when production configuration explicitly enables it.
- [ ] **Step 4: Wire login and conversion limits** to return HTTP 429 with Chinese messages, and build the executor/semaphore from configured one-worker/two-slot defaults.
- [ ] **Step 5: Enforce page count** immediately after opening/decrypt-checking the PDF and before page extraction, raising a user-facing `ConversionError`.
- [ ] **Step 6: Run** `.venv/bin/python -m pytest tests/test_rate_limit.py tests/test_api.py tests/test_converter.py -v` and confirm all cases pass.

### Task 4: Frontend Public-Service Behavior

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: API 401/400/404/429/503 responses from Tasks 2 and 3.
- Produces: authenticated home UX with logout, free-tier/upload notices, 401 redirect, and terminal handling for expired tasks.

- [ ] **Step 1: Add failing web tests** for the 30 MB/100-page notice, free-service wake-up copy, logout control, and JavaScript branches for 401/404/429/503.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_web.py -v` and confirm missing UI behavior fails.
- [ ] **Step 3: Update markup and styling** while preserving the adopted layout and responsive behavior.
- [ ] **Step 4: Update fetch handling** so 401 redirects to `/login`, 404 stops polling with re-upload guidance, and server details for 429/503 are shown once.
- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_web.py tests/test_api.py -v` and confirm pass.

### Task 5: Docker and Render Packaging

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `render.yaml`
- Create: `tests/test_deployment.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `app.main:app`, environment names from Task 1, and `/health` from Task 2.
- Produces: a non-root image command `uvicorn app.main:app --host 0.0.0.0 --port ${PORT}` and a Render Blueprint configured for Docker/free health checks.

- [ ] **Step 1: Write failing descriptor tests** that assert required OCR packages, non-root `USER`, `$PORT`, `/health`, free plan, secret declarations without values, and exclusion of sensitive paths.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_deployment.py -v` and confirm descriptors are absent.
- [ ] **Step 3: Create Dockerfile** installing `tesseract-ocr`, `tesseract-ocr-chi-sim`, `tesseract-ocr-eng`, Chinese fonts and Python dependencies, then dropping to an unprivileged user.
- [ ] **Step 4: Create `.dockerignore` and `render.yaml`** without secret values and with `/health` as the health path.
- [ ] **Step 5: Update README** with safe local environment examples, Docker commands, GitHub/Render steps, free-tier limitations, and troubleshooting.
- [ ] **Step 6: Run descriptor tests**, then build the image with `docker build -t pdf-to-word:local .` if Docker is available.
- [ ] **Step 7: Start the image with temporary generated secrets**, verify HTTP 200 from `/health`, verify `/` redirects before login, and stop the test container.

### Task 6: Full Verification and Secret Audit

**Files:**
- Verify only: all project files

**Interfaces:**
- Consumes: complete Tasks 1-5 implementation.
- Produces: evidence that the project is safe to initialize and publish.

- [ ] **Step 1: Run** `.venv/bin/python -m pytest -v` and require zero failures.
- [ ] **Step 2: Search tracked candidates** for password/token/private-key patterns and verify `说明.txt` contents were never printed or copied.
- [ ] **Step 3: Inspect upload/task runtime directories** and ensure no generated PDF/DOCX is included in source candidates.
- [ ] **Step 4: Review `git diff --check` equivalent** before repository creation, confirming no malformed patch or accidental secret-bearing file.

### Task 7: GitHub Repository Publication

**Files:**
- Create repository metadata: `.git/` (local only)
- Publish tracked project files to a new GitHub repository.

**Interfaces:**
- Consumes: verified publish-safe source tree from Task 6.
- Produces: GitHub repository URL and a verified remote default branch matching local HEAD.

- [ ] **Step 1: Initialize Git** with default branch `main`, then run `git status --short --ignored` and `git check-ignore -v 说明.txt .env .runtime .venv` before staging.
- [ ] **Step 2: Stage explicit safe paths**, inspect `git diff --cached --name-only`, and abort publication if `说明.txt`, secrets, runtime files, PDFs, DOCX files, or virtualenv content appears.
- [ ] **Step 3: Commit** the verified source as the initial commit.
- [ ] **Step 4: Authenticate GitHub safely** through existing GitHub CLI/browser authorization; never parse the password from `说明.txt`. If interactive OAuth is required, ask the user to complete that single browser step.
- [ ] **Step 5: Create a private GitHub repository** named `pdf-to-word-web` unless the name already exists; attach it as `origin` and push `main`.
- [ ] **Step 6: Verify** `git status`, `git rev-parse HEAD`, `git ls-remote origin refs/heads/main`, and the GitHub repository file listing.

### Task 8: Render Deployment and Public End-to-End Acceptance

**Files:**
- No local source changes expected unless deployment reveals a reproducible defect.

**Interfaces:**
- Consumes: GitHub repository and `render.yaml` from Tasks 5 and 7.
- Produces: public Render HTTPS URL with password-protected conversion behavior.

- [ ] **Step 1: Connect the repository in Render** through GitHub OAuth/Blueprint; if browser authentication or a CAPTCHA is required, ask the user to complete it.
- [ ] **Step 2: Set `APP_PASSWORD`** to the user-selected access password and `SESSION_SECRET` to a newly generated value of at least 32 random bytes in Render only.
- [ ] **Step 3: Trigger deployment** and inspect build/runtime logs for OCR language installation, successful Uvicorn startup, `$PORT` binding, and health check success.
- [ ] **Step 4: Verify public unauthenticated behavior**: `/health` returns fixed HTTP 200 JSON, `/` redirects to `/login`, and `/api/tasks/missing` returns 401.
- [ ] **Step 5: Verify public authenticated workflow** with a small generated PDF: login, upload, status polling, completed DOCX download, DOCX ZIP signature/openability, and post-download task deletion.
- [ ] **Step 6: Verify wrong-password rejection** and provide the final HTTPS URL, login/use instructions, and free-tier wake-up/ephemeral-storage limitations.
