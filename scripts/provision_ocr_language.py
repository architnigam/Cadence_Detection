"""Explicit one-time download of an OCR model, never called by extraction."""
from pathlib import Path
import hashlib
import urllib.request

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1]/".local/ocr/eng.traineddata"
    target.parent.mkdir(parents=True, exist_ok=True)
    url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata"
    expected_sha256 = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"
    if not target.exists():
        data = urllib.request.urlopen(url, timeout=60).read()
        if len(data) < 1_000_000:
            raise RuntimeError("Unexpected OCR language download")
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise RuntimeError("OCR model checksum changed; review the upstream model before accepting it")
        temporary = target.with_suffix(".download")
        temporary.write_bytes(data); temporary.replace(target)
    actual_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise RuntimeError("Existing OCR model has an unexpected checksum")
    print("Local English OCR asset SHA256:", actual_sha256)
