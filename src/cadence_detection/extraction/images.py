from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import warnings
from PIL import Image, ImageOps, ImageStat


def open_image(data, extension, max_pixels):
    """Optional local SVG conversion; unsupported EMF is surfaced to the caller."""
    extension = extension.lower()
    if extension == ".svg":
        # External resource references are not fetched. SVG XML entities are disabled by CairoSVG.
        from lxml import etree
        if b"<!DOCTYPE" in data.upper():
            raise ValueError("SVG DOCTYPE requires manual review")
        root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
        for element in root.iter():
            for key, value in element.attrib.items():
                if (key.endswith("href") and not value.startswith(("#", "data:"))) or "url(" in value.lower():
                    raise ValueError("SVG external/CSS resource references require manual review")
            if element.text and ("url(" in element.text.lower() or "@import" in element.text.lower()):
                raise ValueError("SVG CSS resources require manual review")
        try:
            import cairosvg
            data = cairosvg.svg2png(bytestring=data, output_width=1600)
        except ImportError:
            node = os.environ.get("CADENCE_NODE")
            module = os.environ.get("CADENCE_SHARP")
            if not module and os.environ.get("CADENCE_TESSERACT_JS"):
                candidate = Path(os.environ["CADENCE_TESSERACT_JS"]).parent/"sharp"
                module = str(candidate) if candidate.exists() else None
            if not node or not module:
                raise ValueError("SVG needs local CairoSVG or configured Node/Sharp")
            converted = subprocess.run([node, str(Path(__file__).with_name("svg_to_png.cjs")), module,
                                        str(max_pixels)], input=data, capture_output=True, timeout=30, check=False)
            if converted.returncode:
                raise ValueError("Local SVG conversion failed")
            data = converted.stdout
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        image = Image.open(BytesIO(data))
        if image.width * image.height > max_pixels:
            raise ValueError("Image exceeds pixel limit")
        # Animated/multi-page media may carry text in later frames.
        if getattr(image, "n_frames", 1) > 1:
            raise ValueError("Multi-frame image requires explicit frame extraction")
        if extension in (".emf", ".wmf"):
            # Pillow exposes Windows GDI metafile rendering when available. Else fail explicitly.
            base_dpi = image.info.get("dpi", 72)
            if isinstance(base_dpi, tuple):
                base_dpi = base_dpi[0]
            factor = 144/max(1, base_dpi)
            if image.width*image.height*factor*factor > max_pixels:
                raise ValueError("Vector render exceeds pixel limit")
            image.load(dpi=144)
        else:
            image.load()
        if image.width*image.height > max_pixels:
            raise ValueError("Decoded image exceeds pixel limit")
        image = ImageOps.exif_transpose(image)
        if image.mode == "RGBA" or "transparency" in image.info:
            rgba = image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, "white"); bg.alpha_composite(rgba); image = bg
        return image.convert("RGB")


def recognize_image(image, *, result, options, ocr, location, unit=None,
                    bbox=None, coordinate_space="image_pixels_top_left", sparse=False, attributes=None):
    if image.width * image.height > options.max_image_pixels:
        result.issue("IMAGE_LIMIT", "Image exceeds configured pixel limit", location)
        return
    if ocr is None:
        result.issue("OCR_UNAVAILABLE", "Image content needs a configured local OCR engine", location)
        return
    original_size = image.size
    # A small text screenshot is enlarged for OCR. Boxes are mapped back to original pixels.
    scale = min(3.0, max(1.0, 1600/max(image.size)))
    if int(image.width*scale)*int(image.height*scale) > options.max_image_pixels:
        scale = 1.0
    if scale > 1:
        image = image.resize((round(image.width*scale), round(image.height*scale)), Image.Resampling.LANCZOS)
    try:
        lines = ocr.recognize(image, sparse=sparse)
    except Exception:
        result.issue("OCR_FAILED", "Local OCR failed; content was not declared complete", location)
        return
    if not lines:
        # Only near-uniform blank images are non-blocking. Logos/photos still need review.
        std = ImageStat.Stat(image.convert("L")).stddev[0]
        if std > 2:
            result.issue("IMAGE_NO_TEXT", "Nonblank image yielded no text; visual review required", location)
        return
    def mapped_box(input_box):
        box = [v/scale for v in input_box]
        if bbox is not None:
            x, y, right, bottom = bbox
            sx, sy = (right-x)/original_size[0], (bottom-y)/original_size[1]
            box = [x+box[0]*sx, y+box[1]*sy, x+box[2]*sx, y+box[3]*sy]
        return box
    for line_index, line in enumerate(lines, 1):
        if not line.text.strip():
            continue
        box = mapped_box(line.bbox)
        line_location = f"{location}:ocr_line:{line_index}"
        confidence = line.confidence
        complete = confidence >= options.min_ocr_confidence
        if not complete:
            result.issue("LOW_OCR_CONFIDENCE", "OCR line is below the configured confidence threshold", line_location)
        line_attrs = {**(line.attributes or {})}
        if "words" in line_attrs:
            line_attrs["words"] = [{**word, "bbox": mapped_box(word["bbox"])} for word in line_attrs["words"]]
        result.add(line.text, "ocr", line_location, unit, bbox=box, coordinate_space=coordinate_space,
                   ocr_confidence=confidence, extraction_complete=complete,
                   attributes={**(attributes or {}), **line_attrs, "ocr_upscale": scale})
