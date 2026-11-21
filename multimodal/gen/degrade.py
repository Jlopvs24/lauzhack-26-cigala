"""Turn a clean PDF into realistic captures: scanned page, phone photo, low-res image."""
from __future__ import annotations

import random

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image


def rasterize(pdf_path, dpi: int) -> np.ndarray:
    pdf = pdfium.PdfDocument(str(pdf_path))
    img = pdf[0].render(scale=dpi / 72).to_pil().convert("RGB")
    pdf.close()
    return np.array(img)


def _rotate(img: np.ndarray, deg: float, border=(255, 255, 255)) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=border, flags=cv2.INTER_LINEAR)


def scan(pdf_path, rng: random.Random) -> Image.Image:
    img = rasterize(pdf_path, rng.choice([150, 170, 200]))
    img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    img = _rotate(img, rng.uniform(-3.0, 3.0), (245, 245, 245))
    img = cv2.GaussianBlur(img, (3, 3), rng.uniform(0.3, 0.9))
    noise = np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, rng.uniform(4, 10), img.shape)
    img = np.clip(img.astype(np.float32) * rng.uniform(0.92, 1.0) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def photo(pdf_path, rng: random.Random) -> Image.Image:
    page = rasterize(pdf_path, rng.choice([110, 130, 150]))
    h, w = page.shape[:2]
    pad = int(0.08 * w)
    bg = np.full((h + 2 * pad, w + 2 * pad, 3), [rng.randint(60, 120), rng.randint(50, 100), rng.randint(40, 90)], np.uint8)
    bg[pad:pad + h, pad:pad + w] = page
    H2, W2 = bg.shape[:2]
    j = lambda: rng.uniform(-0.045, 0.045)
    src = np.float32([[0, 0], [W2, 0], [W2, H2], [0, H2]])
    dst = np.float32([[W2 * j() + W2 * 0.02, H2 * j() + H2 * 0.02], [W2 * (1 + j()) - W2 * 0.02, H2 * j()],
                      [W2 * (1 + j()), H2 * (1 + j())], [W2 * j(), H2 * (1 + j()) - H2 * 0.02]])
    img = cv2.warpPerspective(bg, cv2.getPerspectiveTransform(src, dst), (W2, H2), borderValue=(70, 60, 50))
    # uneven lighting: a soft diagonal shadow
    yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
    ang = rng.uniform(0, np.pi)
    grad = (np.cos(ang) * xx / W2 + np.sin(ang) * yy / H2)
    grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-6)
    light = 1.0 - rng.uniform(0.15, 0.35) * grad
    warm = np.array([1.0, rng.uniform(0.95, 1.0), rng.uniform(0.85, 0.95)], np.float32)
    img = np.clip(img.astype(np.float32) * light[..., None] * warm, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), rng.uniform(0.5, 1.1))
    return Image.fromarray(img)


def lowres(pdf_path, rng: random.Random) -> Image.Image:
    img = rasterize(pdf_path, rng.choice([72, 80, 90]))
    img = _rotate(img, rng.uniform(-1.0, 1.0))
    return Image.fromarray(img)


VARIANTS = {"scan": scan, "photo": photo, "lowres": lowres}
