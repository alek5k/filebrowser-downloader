import getpass
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class FBContext:
    base_url: str
    share_id: str
    password: Optional[str] = None
    verbose: bool = True
    raise_on_error: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def make_context(base_url: str,
                 password: Optional[str] = None,
                 verbose: bool = True,
                 raise_on_error: bool = False) -> FBContext:
    """
    Initialize a downloader context from a Filebrowser share URL.
    """
    if "/share/" not in base_url:
        raise ValueError("Invalid Filebrowser share URL (missing /share/).")

    base, share_id = base_url.split("/share/", 1)
    return FBContext(base, share_id, password, verbose, raise_on_error)


def fetch_metadata(ctx: FBContext, extra_path: Optional[str] = "") -> dict:
    """
    Fetch metadata from Filebrowser API.
    """
    encoded_path = quote(extra_path or "")
    if extra_path and extra_path.endswith("/") and not encoded_path.endswith("%2F"):
        encoded_path += "%2F"

    meta_url = f"{ctx.base_url}/api/public/share/{ctx.share_id}{encoded_path}"

    need_retry = False
    try:
        req = Request(meta_url, headers=ctx.headers)
        with urlopen(req) as resp:
            return json.load(resp)
    except HTTPError as e:
        if e.code != 401:
            raise
        need_retry = True
    except URLError as e:
        if ctx.raise_on_error:
            raise RuntimeError(f"Failed to fetch metadata ({e})") from e
        return {}

    if need_retry and ctx.password is None:
        print("🔒 This share is password protected.")
        ctx.password = getpass.getpass("Enter password: ")

    if need_retry:
        ctx.headers["X-SHARE-PASSWORD"] = ctx.password
        req = Request(meta_url, headers=ctx.headers)
        try:
            with urlopen(req) as resp:
                return json.load(resp)
        except HTTPError as e:
            print("❌ Failed to access share, possibly incorrect password.")
            if ctx.raise_on_error:
                raise RuntimeError(f"Failed to fetch metadata ({e})") from e
        return {}

    return {}


def download_file(ctx: FBContext, meta: dict, dest: Path, abort_if_exists: bool = True) -> Path:
    filename = Path(meta["name"]).name
    filepath = dest / filename

    file_size_match = filepath.stat().st_size == meta.get("size", 0) if filepath.exists() else False

    if abort_if_exists and filepath.exists() and file_size_match:
        if ctx.verbose:
            print(f"⏩ Skipping: {filepath} already exists")
        return filepath
    elif abort_if_exists and filepath.exists() and not file_size_match:
        if ctx.verbose:
            print(f"⚠️  Warning: {filepath} exists but size mismatch, re-downloading...")

    encoded_path = quote(meta["path"])
    dl_url = f"{ctx.base_url}/api/public/dl/{ctx.share_id}{encoded_path}"

    temp_filepath = filepath.with_suffix(filepath.suffix + ".part")

    try:
        req = Request(dl_url, headers=ctx.headers)
        with urlopen(req) as resp, open(temp_filepath, "wb") as f:
            total_size = resp.length or 0
            downloaded = 0
            block_size = 8192

            if ctx.verbose:
                print(f"⬇️  Downloading {filename}: 0% complete", end="")

            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and ctx.verbose:
                    percent = downloaded * 100 // total_size
                    print(f"\r⬇️  Downloading {filename}: {percent}% complete", end="")
        if ctx.verbose:
            print(f"\r⬇️  Downloading {filename}: 100% complete")
            print(f"✅ File saved: {filepath}")
        temp_filepath.rename(filepath)
        return filepath

    except Exception as e:
        if temp_filepath.exists():
            temp_filepath.unlink()
            if ctx.verbose:
                print()
                print("❌ Error during download, part file removed.")
        if ctx.raise_on_error:
            raise RuntimeError(f"Download failed: {e}")


def download_folder(ctx: FBContext, meta: dict, dest: Path, abort_if_exists: bool = True):
    folder_path = dest / Path(meta["name"]).name

    if ctx.verbose and not folder_path.exists():
        print("📁 Creating folder:", folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    for item in meta.get("items", []):
        if item["isDir"]:
            sub_meta = fetch_metadata(ctx, extra_path=item["path"].rstrip("/") + "/")
            download_folder(ctx, sub_meta, folder_path, abort_if_exists)
        else:
            download_file(ctx, item, folder_path, abort_if_exists)


def download(base_url: str,
             password: Optional[str] = None,
             destination_folder: Optional[str | Path] = None,
             abort_if_exists: bool = True,
             verbose: bool = True,
             raise_on_error: bool = False) -> Path:
    """
    Download a file or folder from the Filebrowser share.
    """
    ctx = make_context(base_url, password, verbose, raise_on_error)

    if verbose:
        print(f"🔗 Starting download for share: {ctx.base_url}/share/{ctx.share_id}")

    meta = fetch_metadata(ctx)
    if not meta:
        return

    is_directory = meta.get("isDir", False)

    if is_directory and destination_folder is None:
        destination_folder = Path.cwd().joinpath(ctx.share_id)
    elif not is_directory and destination_folder is None:
        destination_folder = Path.cwd()
    else:
        destination_folder = Path(destination_folder)

    destination_folder.mkdir(parents=True, exist_ok=True)

    if is_directory:
        download_folder(ctx, meta, destination_folder, abort_if_exists)
        return destination_folder
    else:
        return download_file(ctx, meta, destination_folder, abort_if_exists)

