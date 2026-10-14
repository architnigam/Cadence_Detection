"""Supported real pipeline; each invocation owns its inputs, adapters and OCR worker."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import re
from pathlib import Path
import tempfile

from .extraction import extract_document, ExtractionOptions
from .extraction.ocr import default_ocr
from .detection.comprehensive import ComprehensiveDetector
from .ingestion import contracts as c
from .ingestion.orchestrator import PipelineOrchestrator
from .redaction.models import Block as RBlock
from .redaction.redactor import TextRedactor
from .redaction.gate import SafeReleaseGate

ROOT=Path(__file__).resolve().parents[2]


class RunContext:
    def __init__(self,source,filename,options,ocr,progress):
        self.source,self.filename,self.options,self.ocr=source,filename,options,ocr
        self.progress=progress or (lambda stage:None)
        self.extraction=None; self.blocks=[]; self.findings=[]; self.preview=[]; self.categories={}; self.gate=None
        self.detector=ComprehensiveDetector()


class RealExtractionAdapter:
    def __init__(self,context): self.ctx=context
    def extract(self,manifest,config):
        x=self.ctx; x.progress('Extracting text and running local OCR')
        if isinstance(x.source,bytes):
            with tempfile.TemporaryDirectory(prefix='cadence-upload-') as temporary:
                path=Path(temporary)/('input.'+manifest.detected_format.value)
                path.write_bytes(x.source)
                extraction=extract_document(path,options=x.options,ocr=x.ocr)
        else: extraction=extract_document(x.source,options=x.options,ocr=x.ocr)
        x.extraction=extraction
        blocks=[]
        for b in extraction.blocks:
            kind={'ocr':'ocr_image_region','slide_text':'slide_shape','speaker_notes':'slide_notes','textbox':'text_box','header':'header_footer','footer':'header_footer'}.get(b.source_kind,b.source_kind)
            box=None if b.bbox is None else c.BoundingBox(*b.bbox,coord_system=b.coordinate_space)
            blocks.append(c.NormalizedBlock(manifest.document_id,manifest.document_id+':'+b.block_id.split(':')[-1],
                          b.page_or_slide,kind,b.reading_order,b.text,b.table_row,b.table_column,box,
                          None if b.ocr_confidence is None else b.ocr_confidence/100,b.extraction_complete,
                          {'source_location':b.source_location,'coordinate_space':b.coordinate_space,'attributes':b.attributes}))
        x.blocks=blocks
        confidence=[b.ocr_confidence for b in blocks if b.ocr_confidence is not None]
        unsupported=[i.code for i in extraction.issues if i.code in ('OFFICE_IMAGE_UNSUPPORTED','OFFICE_EMBEDDED_OBJECT','OFFICE_ATTACHMENT','OFFICE_CHART_DIAGRAM','PDF_ATTACHMENTS','PDF_FORMS','PDF_ANNOTATIONS')]
        return c.ExtractionResult(manifest.document_id,blocks,extraction.extraction_complete,
                    sum(confidence)/len(confidence) if confidence else None,bool(unsupported),unsupported,
                    [i.code for i in extraction.issues if i.severity!='info'],{'coverage':extraction.to_dict()['coverage']})


class RealDetectionAdapter:
    def __init__(self,context): self.ctx=context
    def detect(self,blocks,config):
        x=self.ctx; x.progress('Detecting and classifying PII')
        findings=x.detector.detect_blocks(blocks)
        x.findings=[c.PIIFinding(f'f{i+1}',f.document_id,f.block_id,f.entity_type,f.start,f.end,f.confidence,f.detector) for i,f in enumerate(findings)]
        return c.DetectionResult(blocks[0].document_id if blocks else '',x.findings,dict(Counter(f.entity_type for f in findings)),
                                 [] if x.detector.ner_available else ['LOCAL_NER_UNAVAILABLE'],{'complete':x.detector.ner_available})


class RealRedactionAdapter:
    def __init__(self,context): self.ctx=context
    def redact(self,blocks,findings,config):
        x=self.ctx; x.progress('Masking sensitive spans')
        converted=[RBlock(b.document_id,b.block_id,b.page_or_slide,b.source_kind,b.reading_order,b.text,
                          b.table_row,b.table_column,None,b.ocr_confidence,b.extraction_complete) for b in blocks]
        sanitized,mapping,categories=TextRedactor().redact_document(converted,findings)
        x.preview=sanitized; x.categories=categories
        out=[c.RedactedBlock(b.block_id,b.page_or_slide,b.source_kind,b.reading_order,b.text) for b in sanitized]
        # Do not serialize the reversible mapping; hash only tokens/counts for audit identity.
        digest=hashlib.sha256(json.dumps(sorted(mapping.values())).encode()).hexdigest()
        return c.RedactionResult(blocks[0].document_id if blocks else '',out,sum(categories.values()),categories,digest)


class RealRescanAdapter:
    def __init__(self,context): self.ctx=context
    def rescan(self,blocks,config):
        x=self.ctx; x.progress('Verifying redaction and release conditions')
        originals=[RBlock(b.document_id,b.block_id,b.page_or_slide,b.source_kind,b.reading_order,b.text,
                         OCR_confidence=b.ocr_confidence,extraction_complete=b.extraction_complete) for b in x.blocks]
        x.gate=SafeReleaseGate(min_ocr_confidence=x.options.min_ocr_confidence/100,require_ner=True).evaluate(
            x.preview,detection_complete=x.detector.ner_available,original_blocks=originals,expected_findings=x.findings)
        return c.RescanResult(x.blocks[0].document_id if x.blocks else '',x.gate.status=='APPROVED',x.gate.residual_pii_count)


def process_document(source,*,filename=None,options=None,ocr=None,progress=None):
    """Return a public response and a restricted local review object. No external LLM calls."""
    options=options or ExtractionOptions()
    owned=ocr is None; ocr=ocr if ocr is not None else default_ocr()
    ctx=RunContext(source,filename,options,ocr,progress)
    extraction=RealExtractionAdapter(ctx)
    engine=PipelineOrchestrator(config={'analyze_quarantined':True,'ocr':{'min_ocr_confidence_threshold':options.min_ocr_confidence/100},'version':'0.2.0'},
        extraction_adapters={kind:extraction for kind in c.SupportedFormat},pii_detector=RealDetectionAdapter(ctx),
        redaction_adapter=RealRedactionAdapter(ctx),rescan_adapter=RealRescanAdapter(ctx))
    try:
        response=engine.process_file(source,filename)
        response.summary.update({'detected_occurrences':len(ctx.findings),'masked_ranges':sum(ctx.categories.values()),
                                 'category_counts':ctx.categories,'local_ner_available':ctx.detector.ner_available})
        tokens = set(token for block in ctx.preview for token in re.findall(r'\[([A-Z_]+)_\d+\]', block.text))
        distinct_tokens = set(token for block in ctx.preview for token in re.findall(r'\[([A-Z_]+_\d+)\]', block.text))
        response.summary['distinct_details'] = len(distinct_tokens)
        response.summary['distinct_category_counts'] = {
            kind: sum(token.rsplit('_', 1)[0] == kind for token in distinct_tokens)
            for kind in sorted(tokens)
        }
        if ctx.extraction: response.summary['extraction_coverage']=ctx.extraction.to_dict()['coverage']
        response.audit_report['scope']='Sanitized plain text only; original files and visual regions are not exported.'
        response.audit_report['guarantee']='Configured checks only; independent source review remains necessary.'
        return response,ctx
    finally:
        if owned and ocr is not None: ocr.close()


def run_for_qa(path):
    """Black-box QA contract. A local spy replaces any downstream transmission."""
    response,ctx=process_document(path)
    approved=response.release_decision==c.ReleaseDecision.SAFE_FOR_LLM
    calls=[]
    def local_downstream_spy(text):calls.append(len(text))
    if approved:local_downstream_spy(response.sanitized_text)
    return {'status':'approved' if approved else response.status.value,'sanitized_blocks':response.sanitized_blocks,
            'extraction_complete':bool(ctx.extraction and ctx.extraction.extraction_complete),
            'verification_passed':bool(ctx.gate and ctx.gate.status=='APPROVED'),
            'remaining_candidate_count':ctx.gate.residual_pii_count if ctx.gate else 0,
            'downstream_called':bool(calls)}
