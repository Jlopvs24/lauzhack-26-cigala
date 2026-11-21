"""Local, free text acquisition: native PDF text layer first, on-device OCR otherwise.

No network, no tokens. Returns layout-preserving lines (boxes on the same visual
line joined left-to-right after de-skewing) plus OCR confidence per line.
"""
from __future__ import annotations

import io
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

_OCR = None
_OCR_LOCK = threading.Lock()  # one ONNX OCR session, shared; LLM calls still run in parallel
MAX_SIDE = 1800


def _ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


@dataclass
class TextResult:
    text: str
    lines: list[tuple[str, float]]   # (line text, mean OCR confidence; 1.0 for native PDF text)
    method: str                       # pdf_text | ocr
    seconds: float

    @property
    def mean_conf(self) -> float:
        return float(np.mean([c for _, c in self.lines])) if self.lines else 0.0


def load_image(data: bytes | str | Path) -> Image.Image:
    img = Image.open(io.BytesIO(data) if isinstance(data, bytes) else data).convert("RGB")
    s = MAX_SIDE / max(img.size)
    if s < 1 or s > 1.3:  # shrink huge photos; upscale tiny captures so OCR sees bigger glyphs
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS if s < 1 else Image.BICUBIC)
    return img


def _pdf_bytes(path_or_bytes) -> bytes:
    return path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def pdf_text(data: bytes) -> str:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    out = []
    for page in pdf:
        tp = page.get_textpage()
        out.append(tp.get_text_range())
        tp.close()
    pdf.close()
    return "\n".join(out).replace("\r\n", "\n").strip()


def pdf_to_image(data: bytes, dpi: int = 200) -> Image.Image:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    img = pdf[0].render(scale=dpi / 72).to_pil().convert("RGB")
    pdf.close()
    return img


def ocr_lines(img: Image.Image) -> list[tuple[str, float]]:
    with _OCR_LOCK:
        res, _ = _ocr()(np.array(img))
    if not res:
        return []
    boxes = []
    angles = []
    for box, txt, conf in res:
        b = np.array(box, dtype=np.float32)
        (x0, y0), (x1, y1) = b[0], b[1]
        if x1 - x0 > 40:
            angles.append(math.atan2(y1 - y0, x1 - x0))
        boxes.append((b, txt, float(conf)))
    ang = float(np.median(angles)) if angles else 0.0
    ca, sa = math.cos(-ang), math.sin(-ang)
    items = []
    for b, txt, conf in boxes:
        c = b.mean(axis=0)
        x = c[0] * ca - c[1] * sa
        y = c[0] * sa + c[1] * ca
        h = float(np.linalg.norm(b[3] - b[0]))
        left = float((b[:, 0] * ca - b[:, 1] * sa).min())
        items.append((y, left, h, txt, conf))
    items.sort()
    lines: list[list] = []
    for it in items:
        if lines and abs(it[0] - lines[-1][-1][0]) < 0.55 * max(it[2], lines[-1][-1][2]):
            lines[-1].append(it)
        else:
            lines.append([it])
    out = []
    for ln in lines:
        ln.sort(key=lambda t: t[1])
        out.append(("   ".join(t[3] for t in ln), float(np.mean([t[4] for t in ln]))))
    return out


def get_text(src: bytes | str | Path) -> TextResult:
    t0 = time.perf_counter()
    data = _pdf_bytes(src) if not isinstance(src, bytes) else src
    if is_pdf(data):
        txt = pdf_text(data)
        if len(txt) > 40:
            lines = [(ln, 1.0) for ln in txt.splitlines() if ln.strip()]
            return TextResult("\n".join(l for l, _ in lines), lines, "pdf_text", time.perf_counter() - t0)
        img = pdf_to_image(data)
    else:
        img = load_image(data)
    lines = ocr_lines(img)
    return TextResult("\n".join(l for l, _ in lines), lines, "ocr", time.perf_counter() - t0)
