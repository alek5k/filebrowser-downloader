from __future__ import annotations

import getpass
import json
from http.cookies import SimpleCookie
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

@dataclass
class UploaderContext:
    base_url: str
    auth_token: str
    tus_version: str = "1.0.0"
    cookie_token: Optional[str] = None
    verbose: bool = True
    raise_on_error: bool = False
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.headers = {
            "Tus-Resumable": self.tus_version,
            "X-Auth": self.auth_token,
        }
        if self.cookie_token:
            self.headers["Cookie"] = f"auth={self.cookie_token}"


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _normalize_remote_folder(remote_folder: Optional[str]) -> str:
    if not remote_folder:
        return ""
    normalized = remote_folder.replace("\\", "/")
    stripped = normalized.strip("/")
    if not stripped:
        return ""
    return "/".join(quote(part) for part in stripped.split("/"))


def _request(
    method: str,
    url: str,
    headers: dict[str, str],
    data: Optional[bytes] = None,
) -> tuple[int, dict[str, str], bytes]:
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def _extract_auth_cookie(set_cookie_headers: Optional[list[str]]) -> Optional[str]:
    if not set_cookie_headers:
        return None

    for header in set_cookie_headers:
        jar = SimpleCookie()
        jar.load(header)
        morsel = jar.get("auth")
        if morsel is not None:
            return morsel.value
    return None


def _is_jwt_like(value: Optional[str]) -> bool:
    if not value:
        return False
    token = value.strip()
    return token.count(".") == 2


def _login_with_password(
    base_url: str,
    username: str,
    password: str,
) -> tuple[str, Optional[str]]:
    login_url = f"{base_url}/api/login"
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/plain, application/json",
    }
    req = Request(login_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req) as resp:
            payload = resp.read()
            text_payload = payload.decode("utf-8", errors="replace").strip()
            token: Optional[str] = text_payload if _is_jwt_like(text_payload) else None

            set_cookie_headers = resp.headers.get_all("Set-Cookie")
            cookie_token = _extract_auth_cookie(set_cookie_headers)

            if not token:
                raise RuntimeError(
                    "Login response did not include a valid plain-text JWT token."
                )
            return token, cookie_token
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:240] if body else str(exc)
        raise RuntimeError(f"Login failed with status {exc.code}: {detail}") from exc


def _create_upload(ctx: UploaderContext, create_url: str, file_size: int) -> None:
    headers = {
        **ctx.headers,
        "Upload-Length": str(file_size),
    }
    _request("POST", create_url, headers=headers, data=b"")


def _head_offset(ctx: UploaderContext, upload_url: str) -> int:
    status, headers, _ = _request("HEAD", upload_url, headers=ctx.headers)
    if status not in (200, 204):
        raise RuntimeError(f"Unexpected HEAD status: {status}")

    offset = headers.get("Upload-Offset")
    if offset is None:
        raise RuntimeError("Missing Upload-Offset in HEAD response.")
    return int(offset)


def _patch_chunk(ctx: UploaderContext, upload_url: str, offset: int, chunk: bytes) -> int:
    headers = {
        **ctx.headers,
        "Upload-Offset": str(offset),
        "Content-Type": "application/offset+octet-stream",
    }
    status, resp_headers, _ = _request("PATCH", upload_url, headers=headers, data=chunk)
    if status != 204:
        raise RuntimeError(f"Unexpected PATCH status: {status}")

    next_offset = resp_headers.get("Upload-Offset")
    if next_offset is None:
        return offset + len(chunk)
    return int(next_offset)


def upload(
    base_url: str,
    local_file: str | Path,
    remote_folder: Optional[str] = None,
    auth_token: Optional[str] = None,
    cookie_token: Optional[str] = None,
    override: bool = False,
    chunk_size: int = 8 * 1024 * 1024,
    tus_version: str = "1.0.0",
    verbose: bool = True,
    raise_on_error: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Upload a file using Filebrowser's TUS endpoint.

    Parameters:
    - base_url: Filebrowser host root. Example: https://filebrowser.example.com
    - local_file: Local file path to upload.
    - remote_folder: Destination folder relative to Filebrowser root.
    - auth_token: Token used in the X-Auth header. If omitted, username/password login is used.
    - cookie_token: Optional token used in Cookie: auth=<token>.
    - override: Whether to overwrite an existing remote file.
    - chunk_size: Size of each PATCH chunk in bytes.
    - tus_version: Value for the Tus-Resumable header (default: 1.0.0).
    - verbose: Print upload progress.
    - raise_on_error: Raise exceptions instead of returning failures silently.
    - username: Account username for password auth via /api/login.
    - password: Account password for password auth. Prompted if username is set and password is None.
    """
    file_path = Path(local_file).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Local file not found: {file_path}")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if not tus_version.strip():
        raise ValueError("tus_version must be a non-empty string.")

    base = _normalize_base_url(base_url)
    resolved_auth_token = auth_token
    resolved_cookie_token = cookie_token

    if not resolved_auth_token:
        if not username:
            raise ValueError(
                "Provide auth_token or username/password for authenticated uploads."
            )
        if password is None:
            if verbose:
                print("🔐 Upload requires account credentials.")
            password = getpass.getpass("Enter account password: ")
        try:
            resolved_auth_token, login_cookie = _login_with_password(
                base_url=base,
                username=username,
                password=password,
            )
            if resolved_cookie_token is None:
                resolved_cookie_token = login_cookie
            if verbose:
                print(f"🔐 Authenticated as {username}")
        except (HTTPError, URLError, RuntimeError) as exc:
            if raise_on_error:
                raise RuntimeError(f"Failed to authenticate uploader ({exc})") from exc
            if verbose:
                print(f"❌ Failed to authenticate uploader: {exc}")
            return ""

    folder = _normalize_remote_folder(remote_folder)
    filename = quote(file_path.name)

    remote_path = f"{folder}/{filename}" if folder else filename
    upload_url = f"{base}/api/tus/{remote_path}"
    create_url = f"{upload_url}?override={'true' if override else 'false'}"

    ctx = UploaderContext(
        base_url=base,
        auth_token=resolved_auth_token,
        tus_version=tus_version,
        cookie_token=resolved_cookie_token,
        verbose=verbose,
        raise_on_error=raise_on_error,
    )

    file_size = file_path.stat().st_size

    try:
        if verbose:
            print(f"⬆️  Initializing upload: {create_url}")
        _create_upload(ctx, create_url, file_size)
    except HTTPError as exc:
        if exc.code in (409, 412):
            if verbose:
                print("ℹ️  Upload already initialized, checking current offset.")
        else:
            if raise_on_error:
                raise RuntimeError(f"Failed to initialize upload ({exc})") from exc
            return ""
    except URLError as exc:
        if raise_on_error:
            raise RuntimeError(f"Failed to initialize upload ({exc})") from exc
        return ""

    try:
        offset = 0
        try:
            offset = _head_offset(ctx, upload_url)
        except HTTPError as exc:
            if exc.code not in (404, 405):
                raise
            # Some deployments disable HEAD; start from offset 0.
            offset = 0

        if offset > file_size:
            raise RuntimeError(
                f"Server offset ({offset}) exceeds local file size ({file_size})."
            )

        with file_path.open("rb") as fh:
            if offset:
                fh.seek(offset)
            while offset < file_size:
                chunk = fh.read(min(chunk_size, file_size - offset))
                if not chunk:
                    break
                offset = _patch_chunk(ctx, upload_url, offset, chunk)
                if verbose and file_size:
                    percent = int(offset * 100 / file_size)
                    print(f"\r⬆️  Uploading {file_path.name}: {percent}% complete", end="")

        if verbose:
            print(f"\r⬆️  Uploading {file_path.name}: 100% complete")
            print(f"✅ Upload complete: {remote_path}")

        return upload_url

    except Exception as exc:
        if verbose:
            print()
            print(f"❌ Upload failed: {exc}")
        if raise_on_error:
            raise RuntimeError(f"Upload failed: {exc}") from exc
        return ""
