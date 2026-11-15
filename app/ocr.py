"""On-device OCR with Apple's Vision framework (works with WiFi off)."""

from __future__ import annotations

from pathlib import Path

import Quartz
import Vision
from Foundation import NSURL

# Resolve pyobjc's lazy symbols once at import so worker threads never race on them.
_ = (Quartz.CGImageSourceCreateWithURL, Quartz.CGImageSourceCreateImageAtIndex,
     Vision.VNRecognizeTextRequest, Vision.VNImageRequestHandler, Vision.VNRequestTextRecognitionLevelAccurate)


def ocr_image(path: str | Path) -> list[dict]:
    """Return text lines with bounding boxes (x, y, w, h as 0-1 fractions, top-left origin)."""
    url = NSURL.fileURLWithPath_(str(path))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    req.setRecognitionLanguages_(["en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed: {err}")
    lines = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        bb = obs.boundingBox()  # bottom-left origin
        x, y, w, h = bb.origin.x, bb.origin.y, bb.size.width, bb.size.height
        lines.append({
            "text": str(cand[0].string()),
            "conf": float(cand[0].confidence()),
            "box": [round(x, 4), round(1 - y - h, 4), round(w, 4), round(h, 4)],
        })
    lines.sort(key=lambda l: (round(l["box"][1], 2), l["box"][0]))
    return lines
