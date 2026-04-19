"""Tests for app initialization helpers."""

import base64
import json
import os

import pytest

import app as app_module


def _encode_credentials(payload):
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


@pytest.fixture(autouse=True)
def reset_gcp_credential_state(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    app_module._creds_path = None
    yield
    if app_module._creds_path and os.path.exists(app_module._creds_path):
        os.remove(app_module._creds_path)
    app_module._creds_path = None


def test_setup_gcp_credentials_creates_file_and_registers_cleanup(monkeypatch):
    payload = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "abc123",
    }
    key_json = json.dumps(payload)
    monkeypatch.setenv(
        "GOOGLE_APPLICATION_CREDENTIALS_JSON", _encode_credentials(payload)
    )

    cleanup_callbacks = []
    monkeypatch.setattr(app_module.atexit, "register", cleanup_callbacks.append)

    app_module._setup_gcp_credentials()

    path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    assert app_module._creds_path == path
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        assert f.read() == key_json

    assert len(cleanup_callbacks) == 1
    cleanup_callbacks[0]()
    assert not os.path.exists(path)


def test_setup_gcp_credentials_reuses_existing_temp_file(monkeypatch, tmp_path):
    existing_path = tmp_path / "existing-test-creds.json"
    existing_path.write_text('{"type": "service_account"}', encoding="utf-8")
    app_module._creds_path = str(existing_path)
    payload = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "abc123",
    }
    monkeypatch.setenv(
        "GOOGLE_APPLICATION_CREDENTIALS_JSON", _encode_credentials(payload)
    )

    mkstemp_called = {"called": False}

    def _unexpected_mkstemp(*args, **kwargs):
        mkstemp_called["called"] = True
        raise AssertionError(
            "mkstemp should not be called when reusing credential path"
        )

    monkeypatch.setattr(app_module.tempfile, "mkstemp", _unexpected_mkstemp)

    app_module._setup_gcp_credentials()

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(existing_path)
    assert mkstemp_called["called"] is False


def test_setup_gcp_credentials_recreates_when_cached_path_is_missing(
    monkeypatch, tmp_path
):
    missing_path = tmp_path / "missing-test-creds.json"
    app_module._creds_path = str(missing_path)
    payload = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "abc123",
    }
    monkeypatch.setenv(
        "GOOGLE_APPLICATION_CREDENTIALS_JSON", _encode_credentials(payload)
    )

    app_module._setup_gcp_credentials()

    new_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    assert new_path != str(missing_path)
    assert os.path.exists(new_path)
    assert app_module._creds_path == new_path


def test_setup_gcp_credentials_raises_on_invalid_payload(monkeypatch):
    invalid_json = base64.b64encode(b"not-json").decode("utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", invalid_json)

    with pytest.raises(
        RuntimeError, match="Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON format"
    ):
        app_module._setup_gcp_credentials()
