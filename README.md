# Filebrowser Downloader

A simple Python utility to download **files or entire folders recursively** from a [Filebrowser](https://github.com/filebrowser/filebrowser/) public share URL.  

Supports:

✅ Password-protected shares  
✅ Recursive folder downloads (preserves structure)  
✅ Progress display for file downloads  
✅ Skipping already downloaded files (with size check)  
✅ Partial file cleanup on error  
✅ Configurable verbosity and error handling  

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
download("https://yourhost/share/def456", password="secret", destination_folder="path/to/folder")
```

---

## Usage Parameters

- **base_url**: The public share URL (`https://host/share/<share_id>`).  
- **password**: Password if the share is protected. If `None` and required, the user is prompted interactively.  
- **destination_folder**: Where to save files/folders. Defaults to `cwd` if it's a file, otherwise a folder is downloaded into a new subdirectory named after the `share_id`
- **abort_if_exists**: Skip files that already exist and match size. If a file exists but size mismatches, it is re-downloaded.  (Default = `True`)
- **verbose**: Show progress, warnings, and status messages.  (Default = `True`)
- **raise_on_error**: If `True`, raises exceptions instead of failing silently/logging.  (Default = `False`)
- **Returns**: Path to the downloaded file or folder.  

---

## Example Output

```
🔗 Starting download for share: https://yourhost/share/abc123
⬇️  Downloading hello.txt: 0% complete
⬇️  Downloading hello.txt: 100% complete
✅ File saved: downloads/hello.txt

🔗 Starting download for share: https://yourhost/share/def456
📁 Creating folder: downloads/def456
⬇️  Downloading data.csv: 100% complete
✅ File saved: downloads/def456/data.csv
```
