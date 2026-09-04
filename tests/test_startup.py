from pathlib import Path


def test_startup_defaults_to_loopback_and_guards_public_binding():
    script = Path("run.sh").read_text(encoding="utf-8")
    assert '--host "${HOST:-127.0.0.1}"' in script
    assert "APP_PASSWORD" in script
    assert "SESSION_SECRET" in script
