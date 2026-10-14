from __future__ import annotations

from pypdf import PdfReader
import pypdfium2 as pdfium
import pypdfium2.raw as raw
from .images import recognize_image


def extract_pdf(path, result, options, ocr):
    reader = PdfReader(path)
    if reader.is_encrypted:
        if not options.password or not reader.decrypt(options.password):
            result.issue("PDF_PASSWORD", "Encrypted PDF requires a valid password", severity="error")
            return
    if len(reader.pages) > options.max_units:
        result.issue("UNIT_LIMIT", "PDF exceeds page limit", severity="error")
        return
    if options.include_metadata and reader.metadata:
        for key, value in reader.metadata.items():
            if isinstance(value, str):
                result.add(value, "metadata", f"pdf:metadata:{key}")
    elif not options.include_metadata:
        result.issue("METADATA_SKIPPED", "Metadata omitted by configuration")
    if reader.trailer.get("/Root", {}).get("/AcroForm"):
        result.issue("PDF_FORMS", "PDF form fields require dedicated field extraction/review")
    try:
        if reader.attachments:
            result.issue("PDF_ATTACHMENTS", "Embedded file attachments require separate extraction/review")
    except Exception:
        result.issue("PDF_ATTACHMENT_AUDIT", "Could not audit PDF attachments")
    document = pdfium.PdfDocument(str(path), password=options.password)
    try:
        if any(p > len(reader.pages) for p in options.ocr_regions):
            result.issue("OCR_REGION_PAGE", "A configured OCR crop refers to a nonexistent page")
        for index, source in enumerate(reader.pages):
            n = index+1; location = f"pdf:page:{n}"
            unit = {"index": n, "location": location, "processed": False, "method": "pending"}
            result.units.append(unit)
            for annotation_index, reference in enumerate(source.get("/Annots", []), 1):
                annotation = reference.get_object()
                action = annotation.get("/A")
                action = action.get_object() if action else {}
                # Only ordinary URI links are fully handled here. Rich annotations,
                # appearance streams and other actions still require review.
                ordinary_link = (
                    annotation.get("/Subtype") == "/Link"
                    and set(annotation) <= {"/Type", "/Subtype", "/Rect", "/F", "/Border", "/BS", "/C", "/H", "/A", "/StructParent", "/P"}
                    and action.get("/S") == "/URI"
                    and set(action) <= {"/Type", "/S", "/URI", "/IsMap"}
                    and isinstance(action.get("/URI"), str)
                )
                if ordinary_link:
                    result.add(action["/URI"], "pdf_link", f"{location}:link:{annotation_index}", n)
                else:
                    result.issue("PDF_ANNOTATIONS", "Annotations may contain extra text or cover content; review required", location)
            page = document[index]
            bitmap = None
            try:
                width, height = page.get_size()
                rotation = page.get_rotation()
                textpage = page.get_textpage()
                try:
                    native = textpage.get_text_range()
                    if native.strip():
                        unit["method"] = "native+image_audit"
                        count = textpage.count_rects()
                        if count:
                            rectangles = [textpage.get_rect(j) for j in range(count)]
                            left = min(r[0] for r in rectangles)
                            bottom = min(r[1] for r in rectangles)
                            right = max(r[2] for r in rectangles)
                            top = max(r[3] for r in rectangles)
                            # Rectangles can be individual glyphs (Google Docs PDFs).
                            # Keep PDFium's complete text and offsets for detection.
                            result.add(native, "pdf_text", location, n,
                                       bbox=[left, height-top, right, height-bottom],
                                       coordinate_space="pdf_points_top_left_unrotated",
                                       attributes={"page_rotation": rotation, "order_basis": "pdf_text_object_order", "bbox_scope": "page_text"})
                        if count == 0:
                            result.add(native, "pdf_text", location, n)
                            result.issue("PDF_TEXT_LOCATION", "Native text has no rectangle mapping", location)
                    else:
                        unit["method"] = "page_ocr"
                finally:
                    textpage.close()
                scale = options.dpi/72
                if width*height*scale*scale > options.max_image_pixels:
                    result.issue("IMAGE_LIMIT", "Rendered page exceeds pixel limit", location)
                    continue
                if not native.strip():
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil().copy()
                    # PDFium rendering applies rotation; boxes refer to the displayed page.
                    recognize_image(image, result=result, options=options, ocr=ocr, location=location,
                                    unit=n, bbox=[0, 0, image.width/scale, image.height/scale],
                                    coordinate_space="pdf_points_top_left_displayed",
                                    attributes={"page_rotation": rotation})
                else:
                    # Audit all image objects, including images nested inside form XObjects.
                    objects = list(page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=15))
                    if rotation and objects:
                        result.issue("PDF_ROTATED_MIXED", "Rotated mixed page requires image position review", location)
                    for j, obj in enumerate(objects):
                        left, bottom, right, top = obj.get_bounds()
                        if bitmap is None:
                            bitmap = page.render(scale=scale)
                        image = bitmap.to_pil()
                        if rotation:
                            # Avoid incorrect unrotated crop mapping; full-page OCR with explicit warning.
                            crop_box = (0, 0, image.width, image.height)
                        else:
                            crop_box = (max(0, round(left*scale)), max(0, round((height-top)*scale)),
                                        min(image.width, round(right*scale)), min(image.height, round((height-bottom)*scale)))
                        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                            result.issue("PDF_IMAGE_BOUNDS", "Image has empty/clipped bounds", location); continue
                        crop = image.crop(crop_box)
                        recognize_image(crop, result=result, options=options, ocr=ocr,
                                        location=f"{location}:image:{j+1}", unit=n,
                                        bbox=[v/scale for v in crop_box], coordinate_space="pdf_points_top_left_displayed",
                                        sparse=True, attributes={"page_rotation": rotation})
                for region_index, region in enumerate(options.ocr_regions.get(n, []), 1):
                    if bitmap is None:
                        bitmap = page.render(scale=scale)
                    image = bitmap.to_pil()
                    crop_box = (round(region[0]*image.width), round(region[1]*image.height),
                                round(region[2]*image.width), round(region[3]*image.height))
                    before = len(result.blocks)
                    recognize_image(image.crop(crop_box), result=result, options=options, ocr=ocr,
                                    location=f"{location}:detail_region:{region_index}", unit=n,
                                    bbox=[v/scale for v in crop_box], coordinate_space="pdf_points_top_left_displayed",
                                    sparse=True, attributes={"supplementary_region": True, "normalized_crop": region})
                    unit.setdefault("detail_region_blocks", 0)
                    unit["detail_region_blocks"] += len(result.blocks)-before
                unit["processed"] = True
            except Exception:
                result.issue("PDF_PAGE_FAILED", "Page extraction failed; other pages were retained", location)
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        document.close()
