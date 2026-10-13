"""Local OCR backends. No uploads or automatic model downloads."""
from __future__ import annotations

import csv
import io
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass


class OCRError(RuntimeError):
    pass


@dataclass
class OCRLine:
    text: str
    bbox: list[float]  # left, top, right, bottom in input-image pixels
    confidence: float
    attributes: dict | None = None


def parse_tsv(tsv: str) -> list[OCRLine]:
    # tesseract.js omits the header; native Tesseract includes it.
    if tsv and not tsv.lstrip().startswith("level\t"):
        tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n" + tsv
    groups = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        try:
            conf = float(row["conf"])
            x, y, w, h = (float(row[k]) for k in ("left", "top", "width", "height"))
            if not all(math.isfinite(v) for v in (conf, x, y, w, h)) or not 0 <= conf <= 100 or min(x, y, w, h) < 0:
                continue
        except (ValueError, KeyError, TypeError):
            continue
        key = tuple(row.get(k) for k in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append((row["text"], [x, y, x+w, y+h], conf))
    lines = []
    for key, words in groups.items():
        # Tesseract's hierarchy order takes precedence over global top/left sorting.
        box = [min(w[1][0] for w in words), min(w[1][1] for w in words),
               max(w[1][2] for w in words), max(w[1][3] for w in words)]
        weight = sum(len(w[0]) for w in words)
        tokens = []
        offset = 0
        for word, word_box, word_conf in words:
            tokens.append({"text": word, "start": offset, "end": offset+len(word),
                           "bbox": word_box, "confidence": word_conf})
            offset += len(word)+1
        lines.append(OCRLine(" ".join(w[0] for w in words), box,
                             sum(len(w[0])*w[2] for w in words)/weight,
                             {"ocr_hierarchy": list(key), "words": tokens}))
    return lines


class TesseractOCR:
    def __init__(self, executable="tesseract", language="eng", language_dir=None, timeout=180):
        self.executable = shutil.which(str(executable)) or str(executable)
        self.language, self.language_dir, self.timeout = language, language_dir, timeout

    def recognize(self, image, *, sparse=False):
        with tempfile.TemporaryDirectory(prefix="cadence-ocr-") as temp:
            path = Path(temp)/"input.png"; image.save(path)
            args = [self.executable, str(path), "stdout", "-l", self.language,
                    "--psm", "11" if sparse else "3"]
            if self.language_dir:
                args += ["--tessdata-dir", str(self.language_dir)]
            args.append("tsv")
            try:
                run = subprocess.run(args, capture_output=True, timeout=self.timeout, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise OCRError("Local Tesseract unavailable or timed out") from exc
            if run.returncode:
                # Do not log stderr: engines may echo source text or filenames.
                raise OCRError("Local Tesseract failed; verify language assets and engine installation")
            return parse_tsv(run.stdout.decode("utf-8", errors="replace"))

    def close(self):
        pass


class NodeTesseractOCR:
    """Persistent local tesseract.js worker. Caller supplies installed module/model paths."""
    def __init__(self, node, module, language_dir, language="eng", timeout=180):
        self.node, self.module = str(node), str(module)
        self.language_dir, self.language, self.timeout = str(language_dir), language, timeout
        self.process = None
        self.responses = queue.Queue()

    def _start(self):
        if self.process is not None:
            return
        if not (Path(self.language_dir)/f"{self.language}.traineddata").is_file():
            raise OCRError("Local OCR language asset is missing; provision it before extraction")
        script = Path(__file__).with_name("tesseract_worker.cjs")
        try:
            self.process = subprocess.Popen(
                [self.node, str(script), self.module, self.language_dir, self.language],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
            )
        except OSError as exc:
            raise OCRError("Cannot start local Node OCR worker") from exc
        process, responses = self.process, self.responses
        def reader():
            for line in process.stdout:
                responses.put(line)
            responses.put(None)
        threading.Thread(target=reader, daemon=True).start()

    def recognize(self, image, *, sparse=False):
        self._start()
        with tempfile.TemporaryDirectory(prefix="cadence-ocr-") as temp:
            path = Path(temp)/"input.png"; image.save(path)
            try:
                self.process.stdin.write(json.dumps({"path": str(path), "sparse": sparse})+"\n")
                self.process.stdin.flush()
                line = self.responses.get(timeout=self.timeout)
                if line is None:
                    raise OCRError("Local OCR worker exited")
                result = json.loads(line)
                if not result.get("ok"):
                    raise OCRError("Local OCR worker failed")
                return parse_tsv(result["tsv"])
            except (OSError, ValueError, queue.Empty, OCRError) as exc:
                self.close()
                raise OCRError("Local OCR worker failed or timed out") from exc

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()
            self.process = None
            self.responses = queue.Queue()


def default_ocr():
    """Environment configuration permits local bundled runtimes without hard-coded user paths."""
    if all(os.environ.get(k) for k in ("CADENCE_NODE", "CADENCE_TESSERACT_JS", "CADENCE_TESSDATA")):
        return NodeTesseractOCR(os.environ["CADENCE_NODE"], os.environ["CADENCE_TESSERACT_JS"], os.environ["CADENCE_TESSDATA"])
    executable = os.environ.get("CADENCE_TESSERACT", "tesseract")
    if shutil.which(executable) or Path(executable).is_file():
        return TesseractOCR(executable, language_dir=os.environ.get("CADENCE_TESSDATA"))
    return None
