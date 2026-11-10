"""``GET /services/github/contents`` reads only remote GitHub repositories.

The route used to treat any value not starting with ``http`` as a local path and
return the text of every file under it. It must now accept only an
``https://github.com/<owner>/<repo>`` URL and never touch the server's filesystem.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.auth.capabilities import get_capability_for_route
from rhesis.backend.app.main import app
from rhesis.backend.app.services import github

ROUTE = "/services/github/contents"

REJECTED = [
    "/etc",
    "/etc/passwd",
    "../",
    "../../etc",
    ".",
    "/app",
    "C:\\Windows",
    "file:///etc/passwd",
    "http://github.com/owner/repo",
    "https://gitlab.com/owner/repo",
    "https://github.com.evil.example/owner/repo",
    "https://evil.example/github.com/owner/repo",
    "https://user:pass@github.com/owner/repo",
    "https://user@github.com/owner/repo",
    "https://github.com:8443/owner/repo",
    "https://api.github.com/owner/repo",
    "https://github.com/owner",
    "https://github.com/",
    "https://github.com/../etc/passwd",
    "https://github.com/owner/..",
    "https://github.com/owner/repo/tree/../../x",
    "https://github.com/owner/repo/tree/main/../../x",
    "ftp://github.com/owner/repo",
    "httpsx://github.com/owner/repo",
    "https://github.com/owner/repo?token=abc",
    "https://github.com/owner/repo#frag",
    "",
]


@pytest.mark.security
@pytest.mark.parametrize("repo_url", REJECTED)
def test_non_github_values_are_rejected(authenticated_client, repo_url):
    with _patch_http() as calls:
        response = authenticated_client.get(ROUTE, params={"repo_url": repo_url})

    assert response.status_code == 400, response.text
    assert calls == []


@pytest.mark.security
def test_local_directory_is_never_read(authenticated_client, tmp_path):
    (tmp_path / "secret.txt").write_text("server-local-secret")

    response = authenticated_client.get(ROUTE, params={"repo_url": str(tmp_path)})

    assert response.status_code == 400
    assert "server-local-secret" not in response.text


def _fake_github(tree, files):
    def fake_get(url):
        resp = MagicMock()
        resp.__enter__.return_value = resp
        if url.startswith("https://api.github.com/"):
            resp.status_code = 200
            resp.json.return_value = {"tree": tree}
            resp.raise_for_status.return_value = None
        else:
            path = url.split("/main/", 1)[1]
            resp.status_code = 200 if path in files else 404
            body = files.get(path, b"")
            resp.iter_bytes.side_effect = lambda chunk_size: iter(
                [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
            )
        return resp

    return fake_get


@contextmanager
def _patch_http(fake=None):
    """Patch both HTTP helpers; yields the list of requested URLs."""
    calls = []

    def record(url):
        calls.append(url)
        return fake(url) if fake else MagicMock()

    with (
        patch.object(github, "_http_get", side_effect=record),
        patch.object(github, "_http_stream", side_effect=record),
    ):
        yield calls


@pytest.mark.security
@pytest.mark.parametrize(
    "repo_url",
    [
        "https://github.com/owner/repo",
        "https://github.com/owner/repo.git",
        "https://github.com/owner/repo/tree/main/src",
    ],
)
def test_valid_github_url_is_read(authenticated_client, repo_url):
    tree = [
        {"type": "blob", "path": "src/app.py", "size": 12},
        {"type": "tree", "path": "src"},
    ]
    fake = _fake_github(tree, {"src/app.py": b"print('hi')\n"})

    with _patch_http(fake) as called:
        response = authenticated_client.get(ROUTE, params={"repo_url": repo_url})

    assert response.status_code == 200, response.text
    assert "print('hi')" in response.json()
    assert called[0] == "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1"
    assert all(
        u.startswith(("https://api.github.com/", "https://raw.githubusercontent.com/"))
        for u in called
    )


@pytest.mark.security
def test_tree_paths_cannot_escape_the_download_dir(tmp_path):
    tree = [{"type": "blob", "path": "../../escaped.txt", "size": 3}]
    fake = _fake_github(tree, {"../../escaped.txt": b"bad"})
    dest = tmp_path / "dl"

    with _patch_http(fake):
        with pytest.raises(ValueError):
            github.download_github_repo("https://github.com/owner/repo", dest)

    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.security
def test_oversized_repository_is_rejected(authenticated_client, monkeypatch):
    monkeypatch.setattr(github, "_MAX_FILES", 2)
    tree = [{"type": "blob", "path": f"f{i}.py", "size": 1} for i in range(5)]
    fake = _fake_github(tree, {f"f{i}.py": b"x" for i in range(5)})

    with _patch_http(fake):
        response = authenticated_client.get(
            ROUTE, params={"repo_url": "https://github.com/owner/repo"}
        )

    assert response.status_code == 400


@pytest.mark.security
def test_each_call_uses_its_own_temp_dir(monkeypatch):
    seen = []

    def fake_download(url, dest):
        seen.append(dest)
        (dest / "a.py").write_text("x = 1\n")

    monkeypatch.setattr(github, "download_github_repo", fake_download)
    github.read_repo_contents("https://github.com/owner/repo")
    github.read_repo_contents("https://github.com/owner/repo")

    assert len(seen) == 2 and seen[0] != seen[1]
    assert not any(p.exists() for p in seen)


@pytest.mark.security
def test_route_requires_service_read_capability():
    route = next(r for r in app.router.routes if getattr(r, "path", None) == ROUTE)
    assert get_capability_for_route(route) == "service:read"


@pytest.mark.security
def test_route_requires_authentication(client):
    response = client.get(ROUTE, params={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code in (401, 403)


@pytest.mark.security
def test_file_body_over_cap_is_skipped(monkeypatch):
    # The tree reports a small size, but the body served is larger than the cap.
    monkeypatch.setattr(github, "_MAX_FILE_BYTES", 10)
    tree = [
        {"type": "blob", "path": "big.py", "size": 1},
        {"type": "blob", "path": "ok.py", "size": 1},
    ]
    fake = _fake_github(tree, {"big.py": b"x" * 100, "ok.py": b"y = 1\n"})

    with _patch_http(fake):
        contents = github.read_repo_contents("https://github.com/owner/repo")

    assert "ok.py" in contents
    assert "big.py" not in contents
