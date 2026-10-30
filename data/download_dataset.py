"""
data/download_dataset.py — Helper script to download FVC2002 DB1_B benchmark dataset.

FVC2002 DB1_B contains real optical fingerprint images:
- 10 fingers (Identities 101 to 110)
- 8 impressions per finger (e.g. 101_1.tif, 101_2.tif ... 110_8.tif)
- Format: TIFF, 388x374 px, 500 dpi, captured with Identix TouchView II optical sensor.
"""

import io
import pathlib
import urllib.request
import zipfile

DATA_DIR = pathlib.Path(__file__).parent / "DB1_B"
URL = "http://bias.csr.unibo.it/fvc2002/Downloads/DB1_B.zip"

def download_and_extract():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(DATA_DIR.glob("*.tif"))
    if len(existing) >= 80:
        print(f"Dataset already present in {DATA_DIR.resolve()} ({len(existing)} images found).")
        return

    print(f"Downloading FVC2002 DB1_B dataset from {URL}...")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    print(f"Downloaded {len(data) / (1024*1024):.2f} MB. Extracting...")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DATA_DIR)

    files = sorted(DATA_DIR.glob("*.tif"))
    print(f"Successfully extracted {len(files)} real fingerprint images to {DATA_DIR.resolve()}.")

if __name__ == "__main__":
    download_and_extract()
