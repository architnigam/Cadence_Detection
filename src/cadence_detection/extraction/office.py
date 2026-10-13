"""OOXML extraction in package order with table, textbox and media provenance."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import posixpath
from lxml import etree
from .images import open_image, recognize_image

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
}
def tag(prefix, name):
    return f"{{{NS[prefix]}}}{name}"

def xml(package, part):
    data = package.read(part)
    if b"<!DOCTYPE" in data.upper():
        raise ValueError("DOCTYPE is not supported in Office XML")
    return etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))

def relationships(package, part):
    relpart = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part)+".rels")
    if relpart not in package.namelist():
        return {}
    out = {}
    for rel in xml(package, relpart):
        target = rel.get("Target", "")
        external = rel.get("TargetMode") == "External"
        resolved = None if external else posixpath.normpath(posixpath.join(posixpath.dirname(part), target.lstrip("/")))
        if target.startswith("/") and not external:
            resolved = target.lstrip("/")
        if resolved and (resolved.startswith("../") or "\\" in resolved):
            raise ValueError("Invalid internal relationship target")
        out[rel.get("Id")] = {"target": resolved, "external": external, "type": rel.get("Type", ""), "raw": target}
    return out

def paragraph_text(element, prefix="w"):
    pieces = []
    for node in element.iter():
        # Text boxes are separate blocks; skip nested textbox paragraphs here.
        if prefix == "w":
            nested_box = False
            for ancestor in node.iterancestors():
                if ancestor is element:
                    break
                if ancestor.tag == tag("w", "txbxContent"):
                    nested_box = True
            if nested_box:
                continue
        if node.tag == tag(prefix, "t"):
            pieces.append(node.text or "")
        elif node.tag == tag(prefix, "tab"):
            pieces.append("\t")
        elif node.tag in (tag(prefix, "br"), tag(prefix, "cr")):
            pieces.append("\n")
    return "".join(pieces)


class OfficeExtractor:
    def __init__(self, package, result, options, ocr):
        self.package, self.result, self.options, self.ocr = package, result, options, ocr
        self.seen_media = set()
        self.image_cache = {}

    def audit_part(self, root, part):
        if root.xpath(".//w:del | .//w:moveFrom | .//w:ins | .//w:vanish", namespaces=NS):
            self.result.issue("OFFICE_REVISIONS_HIDDEN", "Tracked revisions or hidden runs require review", part)
        if root.xpath(".//w:altChunk | .//w:object | .//p:oleObj | .//a:videoFile | .//a:audioFile", namespaces=NS):
            self.result.issue("OFFICE_EMBEDDED_OBJECT", "Embedded objects/media require separate extraction", part)
        if root.xpath(".//a:graphicData[contains(@uri, 'chart') or contains(@uri, 'diagram')]", namespaces=NS):
            self.result.issue("OFFICE_CHART_DIAGRAM", "Chart/SmartArt data requires review beyond text shapes", part)
        for node in root.xpath(".//*[@descr or @title]", namespaces=NS):
            for key in ("descr", "title"):
                if node.get(key):
                    self.result.add(node.get(key), "alt_text", f"{part}:alt:{key}")
        for i, text in enumerate(root.xpath(".//w:instrText/text() | .//w:fldSimple/@w:instr", namespaces=NS), 1):
            self.result.add(text, "field_instruction", f"{part}:field_instruction:{i}")
        for rel in relationships(self.package, part).values():
            if rel["external"]:
                if rel["type"].endswith("/hyperlink"):
                    self.result.add(rel["raw"], "hyperlink_target", f"{part}:hyperlink")
                else:
                    self.result.issue("OFFICE_EXTERNAL_RESOURCE", "External resource was not fetched", part)

    def media(self, root, part, location, unit=None, bbox=None, space="image_pixels_top_left"):
        rels = relationships(self.package, part)
        refs = root.xpath(".//a:blip/@r:embed | .//a:blip/@r:link | .//v:imagedata/@r:id | .//*[local-name()='svgBlip']/@r:embed", namespaces=NS)
        # AlternateContent often repeats a vector asset and a raster fallback; both are audited.
        for i, rid in enumerate(refs, 1):
            rel = rels.get(rid)
            loc = f"{location}:image:{i}:{rid}"
            if not rel or rel["external"] or not rel["target"]:
                self.result.issue("OFFICE_IMAGE_RELATIONSHIP", "Image relationship is missing or external", loc)
                continue
            target = rel["target"]; self.seen_media.add(target)
            try:
                if target not in self.image_cache:
                    self.image_cache[target] = open_image(self.package.read(target), PurePosixPath(target).suffix, self.options.max_image_pixels)
                image = self.image_cache[target]
                recognize_image(image, result=self.result, options=self.options, ocr=self.ocr, location=loc,
                                unit=unit, bbox=bbox, coordinate_space=space, sparse=True,
                                attributes={"media_part": target})
            except Exception:
                self.result.issue("OFFICE_IMAGE_UNSUPPORTED", "Image is damaged, too large, or needs a local vector/frame converter", loc)

    def word_blocks(self, parent, part, location, kind="paragraph", row=None, col=None):
        pindex = tindex = 0
        for child in parent:
            if child.tag == tag("w", "p"):
                pindex += 1; loc = f"{location}:paragraph:{pindex}"
                props = child.find("w:pPr", NS)
                attrs = {}
                if props is not None:
                    style = props.find("w:pStyle", NS)
                    if style is not None:
                        attrs["paragraph_style"] = style.get(tag("w", "val"))
                    if props.find("w:numPr", NS) is not None:
                        attrs["numbering_present"] = True
                        # OOXML list labels are not stored in text. Keep a signal, not invented numbers.
                self.result.add(paragraph_text(child), kind, loc, table_row=row, table_column=col, attributes=attrs)
                self.media(child, part, loc)
                for j, box in enumerate(child.xpath(".//w:txbxContent", namespaces=NS), 1):
                    self.word_blocks(box, part, f"{loc}:textbox:{j}", "textbox", row, col)
            elif child.tag == tag("w", "tbl"):
                tindex += 1; tloc = f"{location}:table:{tindex}"
                for ri, tr in enumerate(child.findall("w:tr", NS)):
                    ci = 0
                    before = tr.find("w:trPr/w:gridBefore", NS)
                    if before is not None:
                        ci = int(before.get(tag("w", "val"), "0"))
                    for tc in tr.findall("w:tc", NS):
                        span = tc.find("w:tcPr/w:gridSpan", NS)
                        merge = tc.find("w:tcPr/w:vMerge", NS)
                        self.word_blocks(tc, part, f"{tloc}:row:{ri}:column:{ci}", "table_cell", ri, ci)
                        if merge is not None:
                            self.result.issue("WORD_MERGED_CELL", "Vertical merge relationship retained by XML location; review table structure", tloc, "info")
                        ci += int(span.get(tag("w", "val"), "1")) if span is not None else 1
            elif child.tag == tag("w", "sdt"):
                content = child.find("w:sdtContent", NS)
                if content is not None:
                    self.word_blocks(content, part, location+":content_control", kind, row, col)
            elif child.tag in (tag("w", "customXml"), tag("w", "ins")):
                self.word_blocks(child, part, location+":container", kind, row, col)
            elif child.tag == tag("w", "altChunk"):
                self.result.issue("WORD_ALTCHUNK", "Alternative document content needs separate extraction", location)

    def docx(self):
        part = "word/document.xml"; root = xml(self.package, part)
        self.result.units.append({"index": 1, "location": part, "processed": False, "method": "native+xml_media"})
        self.audit_part(root, part)
        self.word_blocks(root.find("w:body", NS), part, part)
        # DOCX page breaks depend on layout/rendering; do not fabricate page numbers.
        self.result.issue("WORD_PAGINATION", "DOCX locations are XML paragraph/table paths; rendered page numbers are unavailable", part, "info")
        self.result.units[0]["processed"] = True
        for supplemental in sorted(self.package.namelist()):
            base = PurePosixPath(supplemental).name
            if supplemental.startswith("word/") and supplemental.endswith(".xml") and (
                base.startswith(("header", "footer")) or base in ("comments.xml", "footnotes.xml", "endnotes.xml")
            ):
                extra = xml(self.package, supplemental); self.audit_part(extra, supplemental)
                kind = "header" if base.startswith("header") else "footer" if base.startswith("footer") else base[:-4]
                self.word_blocks(extra, supplemental, supplemental, kind)
                for j, container in enumerate(extra, 1):
                    if container.tag in (tag("w", "comment"), tag("w", "footnote"), tag("w", "endnote")):
                        self.word_blocks(container, supplemental, f"{supplemental}:item:{j}", kind)

    def pptx(self):
        part = "ppt/presentation.xml"; root = xml(self.package, part); rels = relationships(self.package, part)
        slides = root.findall("p:sldIdLst/p:sldId", NS)
        if len(slides) > self.options.max_units:
            self.result.issue("UNIT_LIMIT", "Presentation exceeds slide limit", severity="error"); return
        for number, sid in enumerate(slides, 1):
            rel = rels.get(sid.get(tag("r", "id")))
            unit = {"index": number, "location": rel["target"] if rel else "missing", "processed": False, "method": "native+xml_media"}
            self.result.units.append(unit)
            try:
                slidepart = rel["target"]; slide = xml(self.package, slidepart)
                self.audit_part(slide, slidepart)
                if slide.get("show") == "0":
                    self.result.issue("PPT_HIDDEN_SLIDE", "Hidden slide was included", slidepart, "info")
                tree = slide.find("p:cSld/p:spTree", NS)
                self.shapes(tree, slidepart, number)
                for sr in relationships(self.package, slidepart).values():
                    if sr["type"].endswith("/notesSlide") and not sr["external"]:
                        if not self.options.include_notes:
                            self.result.issue("NOTES_SKIPPED", "Speaker notes excluded by configuration", slidepart)
                            continue
                        notes = xml(self.package, sr["target"]); self.audit_part(notes, sr["target"])
                        self.shapes(notes.find("p:cSld/p:spTree", NS), sr["target"], number, source_kind="speaker_notes")
                unit["processed"] = True
            except Exception:
                self.result.issue("PPT_SLIDE_FAILED", "Slide extraction failed; other slides retained", f"slide:{number}")
        # Master/layout text and images can be visible on every slide. Keep supplemental provenance.
        for name in sorted(self.package.namelist()):
            if name.endswith(".xml") and (name.startswith("ppt/slideMasters/slideMaster") or name.startswith("ppt/slideLayouts/slideLayout")):
                master = xml(self.package, name); self.audit_part(master, name)
                self.shapes(master.find("p:cSld/p:spTree", NS), name, None, source_kind="template_text")
            elif name.startswith("ppt/comments/") and name.endswith(".xml"):
                comment = xml(self.package, name)
                for j, text in enumerate(comment.xpath("//*[local-name()='text']/text()"), 1):
                    self.result.add(text, "comments", f"{name}:comment:{j}")

    def shapes(self, tree, part, unit, transform=(1.0, 1.0, 0.0, 0.0), source_kind="slide_text", location_root=None):
        if tree is None:
            return
        sx, sy, ox, oy = transform
        for index, shape in enumerate(tree, 1):
            loc = f"{location_root or part}:shape:{index}"
            if shape.tag == tag("p", "grpSp"):
                xf = shape.find("p:grpSpPr/a:xfrm", NS)
                new = transform
                if xf is not None:
                    off, ext, choff, chext = (xf.find("a:"+n, NS) for n in ("off", "ext", "chOff", "chExt"))
                    if all(v is not None for v in (off, ext, choff, chext)):
                        gx = int(ext.get("cx"))/max(1, int(chext.get("cx")))
                        gy = int(ext.get("cy"))/max(1, int(chext.get("cy")))
                        new = (sx*gx, sy*gy, ox+sx*(int(off.get("x"))-gx*int(choff.get("x"))),
                               oy+sy*(int(off.get("y"))-gy*int(choff.get("y"))))
                    if xf.get("rot") or xf.get("flipH") == "1" or xf.get("flipV") == "1":
                        self.result.issue("PPT_GROUP_TRANSFORM", "Rotated/flipped group coordinates require review", loc)
                self.shapes(shape, part, unit, new, source_kind, location_root=loc+":group"); continue
            bbox = None
            xf = shape.find("p:spPr/a:xfrm", NS)
            if xf is None:
                xf = shape.find("p:xfrm", NS)
            if xf is not None:
                off, ext = xf.find("a:off", NS), xf.find("a:ext", NS)
                if off is not None and ext is not None:
                    x, y, w, h = int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))
                    bbox = [ox+sx*x, oy+sy*y, ox+sx*(x+w), oy+sy*(y+h)]
                if xf.get("rot") or xf.get("flipH") == "1" or xf.get("flipV") == "1":
                    self.result.issue("PPT_SHAPE_TRANSFORM", "Rotated/flipped shape coordinates require review", loc)
            table = shape.find("a:graphic/a:graphicData/a:tbl", NS)
            if table is not None:
                for ri, row in enumerate(table.findall("a:tr", NS)):
                    for ci, cell in enumerate(row.findall("a:tc", NS)):
                        for pi, para in enumerate(cell.findall("a:txBody/a:p", NS)):
                            self.result.add(paragraph_text(para, "a"), "table_cell", f"{loc}:row:{ri}:column:{ci}:paragraph:{pi+1}", unit,
                                            table_row=ri, table_column=ci, bbox=bbox, coordinate_space="slide_emu_top_left",
                                            attributes={"bbox_scope": "whole_table", "grid_span": cell.get("gridSpan", "1"), "row_span": cell.get("rowSpan", "1")})
            else:
                for pi, para in enumerate(shape.findall("p:txBody/a:p", NS), 1):
                    self.result.add(paragraph_text(para, "a"), source_kind, f"{loc}:paragraph:{pi}", unit,
                                    bbox=bbox, coordinate_space="slide_emu_top_left",
                                    attributes={"order_basis": "shape_xml_order", "bbox_scope": "whole_shape"})
            crop = shape.find(".//a:srcRect", NS)
            if crop is not None and any(int(v) for v in crop.attrib.values()):
                self.result.issue("PPT_IMAGE_CROP", "Full underlying image extracted; cropped image placement requires review", loc)
            self.media(shape, part, loc, unit, bbox, "slide_emu_top_left" if bbox else "image_pixels_top_left")

    def remaining_media_and_metadata(self):
        for name in sorted(self.package.namelist()):
            if (name.startswith("word/media/") or name.startswith("ppt/media/")) and name not in self.seen_media:
                self.result.issue("OFFICE_UNPLACED_MEDIA", "Media asset has no resolved placement; local OCR attempted", name)
                try:
                    image = open_image(self.package.read(name), PurePosixPath(name).suffix, self.options.max_image_pixels)
                    recognize_image(image, result=self.result, options=self.options, ocr=self.ocr, location=name, sparse=True)
                except Exception:
                    self.result.issue("OFFICE_IMAGE_UNSUPPORTED", "Unplaced media needs conversion/review", name)
            if name.startswith(("word/embeddings/", "ppt/embeddings/")):
                self.result.issue("OFFICE_ATTACHMENT", "Embedded attachment requires separate extraction", name)
            if name.lower().endswith("vbaproject.bin"):
                self.result.issue("OFFICE_MACRO", "Macro content was not executed or extracted", name)
        if self.options.include_metadata:
            for name in ("docProps/core.xml", "docProps/custom.xml", "docProps/app.xml"):
                if name in self.package.namelist():
                    root = xml(self.package, name)
                    for i, element in enumerate(root.iter()):
                        if len(element) == 0 and element.text:
                            self.result.add(element.text, "metadata", f"{name}:field:{i}:{etree.QName(element).localname}")
        else:
            self.result.issue("METADATA_SKIPPED", "Metadata omitted by configuration")


def extract_office(package, result, options, ocr):
    extractor = OfficeExtractor(package, result, options, ocr)
    if result.detected_format == "docx":
        extractor.docx()
    else:
        extractor.pptx()
    extractor.remaining_media_and_metadata()
