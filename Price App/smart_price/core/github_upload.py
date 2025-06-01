import base64
import json
import logging
import os
from pathlib import Path
from urllib import request, error
from urllib.parse import quote

logger = logging.getLogger("smart_price")


def _api_request(method: str, url: str, token: str, data: dict | None = None) -> dict:
    req = request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        req.data = payload
    try:
        with request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}
    except error.HTTPError as exc:  # pragma: no cover - network errors
        logger.debug("GitHub API error for %s: %s", url, exc)
        raise
    except Exception as exc:  # pragma: no cover - unexpected failures
        logger.debug("GitHub request failed for %s: %s", url, exc)
        raise


def _sanitize_repo_path(path: str) -> str:
    safe = path.replace(" ", "_")
    return quote(safe, safe="/")


def upload_folder(path: Path, *, remote_prefix: str | None = None) -> bool:
    """Upload ``path`` to a GitHub repository.

    Parameters
    ----------
    path : :class:`~pathlib.Path`
        Local directory to upload.
    remote_prefix : str, optional
        Folder prefix for uploaded files.  When ``None`` (default), files are
        placed under ``"LLM_Output_db/<path.name>"`` in the repository.

    Requires ``GITHUB_REPO`` and ``GITHUB_TOKEN`` environment variables. Set
    ``GITHUB_BRANCH`` to push to a branch other than ``main``.
    """
    repo = os.getenv("GITHUB_REPO")
    token = os.getenv("GITHUB_TOKEN")
    branch = os.getenv("GITHUB_BRANCH", "main")
    if remote_prefix is None:
        remote_prefix = f"LLM_Output_db/{path.name}"
    remote_prefix = _sanitize_repo_path(remote_prefix)
    if not repo or not token:
        logger.info("GitHub repo or token not configured; skipping upload")
        return False

    success = True
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        repo_path = Path(remote_prefix) / file_path.relative_to(path)
        url_path = _sanitize_repo_path(repo_path.as_posix())
        url = f"https://api.github.com/repos/{repo}/contents/{url_path}"
        with open(file_path, "rb") as fh:
            content = base64.b64encode(fh.read()).decode("ascii")
        try:
            resp = _api_request("GET", f"{url}?ref={branch}", token)
            sha = resp.get("sha")
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Failed to fetch existing file %s: %s", repo_path, exc)
            sha = None
        data = {"message": f"Add {repo_path}", "content": content, "branch": branch}
        if sha:
            data["sha"] = sha
        try:
            _api_request("PUT", url, token, data)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Failed to upload %s: %s", repo_path, exc)
            success = False
    return success

