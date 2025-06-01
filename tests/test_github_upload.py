import os
import types
from pathlib import Path

from smart_price.core.github_upload import (
    _sanitize_repo_path,
    upload_folder,
    delete_github_folder,
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

    def fake_api(method, url, token, data=None):
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

    def fake_api(method, url, token, data=None):
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

