import logging
import base64
from urllib import error
import pytest

from smart_price.core.github_upload import (
    _sanitize_repo_path,
    upload_folder,
    delete_github_folder,
    _api_request,
)


def test_sanitize_repo_path():
    path = (
        "LLM_Output_db/Omega Motor Tüm Fiyat Listeleri Mart 2025/"
        "llm_response_page_01.txt"
    )
    sanitized = _sanitize_repo_path(path)
    assert " " not in sanitized
    assert sanitized.startswith(
        "LLM_Output_db/Omega_Motor_T%C3%BCm_Fiyat_Listeleri_Mart_2025"
    )


def test_upload_folder_encodes_url(tmp_path, monkeypatch):
    folder = tmp_path / "Omega Motor Tüm"
    folder.mkdir()
    f = folder / "page.txt"
    f.write_text("x")

    calls = []

    def fake_api(method, url, token, data=None, timeout=None):
        calls.append(url)
        return {}

    monkeypatch.setattr(
        "smart_price.core.github_upload._api_request", fake_api
    )
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    upload_folder(folder, remote_prefix=f"LLM_Output_db/{folder.name}")

    assert calls
    assert "%20" not in calls[0]


def test_delete_github_folder(monkeypatch):
    calls = []

    def fake_api(method, url, token, data=None, timeout=None):
        calls.append((method, url))
        if method == "GET":
            return [
                {
                    "type": "file",
                    "path": "My_folder/file.txt",
                    "sha": "1",
                }
            ]
        return {}

    monkeypatch.setattr(
        "smart_price.core.github_upload._api_request", fake_api
    )
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    delete_github_folder("My folder")

    assert calls[0][0] == "GET"
    assert "My_folder" in calls[0][1]
    assert "%20" not in calls[0][1]
    assert calls[1][0] == "DELETE"


def test_upload_folder_404_no_error(monkeypatch, tmp_path, caplog):
    folder = tmp_path / "Omega"
    folder.mkdir()
    f = folder / "page.txt"
    f.write_text("x")

    calls = []

    def fake_api(method, url, token, data=None, timeout=None):
        calls.append(method)
        if method == "GET":
            raise error.HTTPError(url, 404, "Not Found", None, None)
        return {}

    monkeypatch.setattr(
        "smart_price.core.github_upload._api_request", fake_api
    )
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    with caplog.at_level(logging.ERROR, logger="smart_price"):
        upload_folder(folder, remote_prefix=f"LLM_Output_db/{folder.name}")

    assert calls[0] == "GET"
    assert "PUT" in calls
    assert not caplog.records


def test_api_request_timeout(monkeypatch):
    def fake_open(_req, timeout=None):
        raise TimeoutError("boom")

    monkeypatch.setattr(
        "smart_price.core.github_upload.request.urlopen", fake_open
    )

    with pytest.raises(TimeoutError):
        _api_request("GET", "http://example", "tok", timeout=0.01)


def test_api_request_timeout_env(monkeypatch):
    captured = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def read(self):
            return b"{}"

    def fake_open(_req, timeout=None):
        captured["timeout"] = timeout
        return Resp()

    monkeypatch.setattr(
        "smart_price.core.github_upload.request.urlopen", fake_open
    )
    monkeypatch.setenv("GITHUB_HTTP_TIMEOUT", "12")

    _api_request("GET", "http://example", "tok")
    assert captured["timeout"] == 12


def test_upload_folder_conflict(monkeypatch, tmp_path, caplog):
    folder = tmp_path / "conflict"
    folder.mkdir()
    f = folder / "page.txt"
    f.write_text("same")

    calls = []
    step = {"n": 0}

    def fake_api(method, url, token, data=None, timeout=None):
        calls.append(method)
        if method == "GET":
            if step["n"] == 0:
                step["n"] = 1
                return {"sha": "old"}
            return {"sha": "new", "content": base64.b64encode(b"same").decode("ascii")}
        if method == "PUT" and step["n"] == 1:
            step["n"] = 2
            raise error.HTTPError(url, 409, "Conflict", None, None)
        return {}

    monkeypatch.setattr("smart_price.core.github_upload._api_request", fake_api)
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    with caplog.at_level(logging.ERROR, logger="smart_price"):
        assert upload_folder(folder, remote_prefix=f"LLM_Output_db/{folder.name}")

    assert calls == ["GET", "PUT", "GET"]
    assert not caplog.records

