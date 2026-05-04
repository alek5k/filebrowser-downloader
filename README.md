# Filebrowser Downloader

A simple Python utility to download files or folders from a [Filebrowser](https://github.com/filebrowser/filebrowser/) public share URL.  

Supports:

✅ Password-protected shares  
✅ Recursive folder downloads (preserves structure)  
✅ Progress display for file downloads  
✅ Skipping already downloaded files (with size check)  
✅ Partial file cleanup on error  
✅ Configurable verbosity and error handling

Although primarily intended as a downloader, this utility also **supports file uploads** using username and password auth.

---

## Installation

Download from PyPI:

```bash
pip install filebrowser-downloader
```

---

## Minimal Usage

```python
from filebrowser_downloader import download

# Download a single file into the current working directory:
download("https://yourhost/share/abc123")

# Download a folder (recursively) into path/to/folder
download(
    base_url="https://yourhost/share/def456", 
    password="secret", 
    destination_folder="path/to/folder"
)
```
Parameters:

- **base_url**: The public share URL (`https://host/share/<share_id>`).  
- **password**: Password if the share is protected. If `None` and required, the user is prompted interactively.  
- **destination_folder**: Where to save files/folders. Defaults to `cwd` if it's a file, otherwise a folder is downloaded into a new subdirectory named after the `share_id`
- **abort_if_exists**: Skip files that already exist and match size. If a file exists but size mismatches, it is re-downloaded.  (Default = `True`)
- **verbose**: Show progress, warnings, and status messages.  (Default = `True`)
- **raise_on_error**: If `True`, raises exceptions instead of failing silently/logging.  (Default = `False`)
- **Returns**: Path to the downloaded file or folder.  

---

## Upload Usage

```python
from filebrowser_downloader import upload

upload(
    base_url="https://yourhost",
    local_file="path/to/file.bin",
    remote_folder="my/remote/folder",
    remote_filename="renamed-on-server.bin",  # omit/None to keep local filename
    username="your_username",
    password="your_password",  # omit to prompt interactively
    override=True,
)
```

Notes:
- `remote_folder` is appended to `/api/tus/<remote_folder>/<filename>`.
- `remote_filename` overrides the remote file name; if `None`, `local_file`'s filename is used.
- `override` controls whether remote file is overwritten or kept.
