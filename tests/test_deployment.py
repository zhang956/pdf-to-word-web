from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_docker_build_installs_ocr_and_runs_as_non_root():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "tesseract-ocr-chi-sim" in dockerfile
    assert "tesseract-ocr-eng" in dockerfile
    assert "USER app" in dockerfile
    assert "0.0.0.0" in dockerfile
    assert "${PORT}" in dockerfile


def test_docker_context_excludes_private_and_runtime_files():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "说明.txt" in ignored
    assert ".env" in ignored
    assert ".runtime" in ignored
    assert ".venv" in ignored
    assert ".git" in ignored


def test_render_blueprint_uses_free_docker_service_without_secret_values():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "runtime: docker" in blueprint
    assert "plan: free" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "key: APP_PASSWORD" in blueprint
    assert "key: SESSION_SECRET" in blueprint
    assert "sync: false" in blueprint
    assert "local-dev-password" not in blueprint
