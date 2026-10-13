"""Validated, document-local redaction. Overlapping ranges are unioned."""
from collections import defaultdict
from dataclasses import replace
import math
from .models import Block, Finding


class TextRedactor:
    def __init__(self, token_format='[{entity_type}_{index}]'):
        self.token_format=token_format
        try:
            token=token_format.format(entity_type='PERSON',index=1)
        except (KeyError,ValueError):
            raise ValueError('Invalid placeholder format') from None
        if not token.strip(): raise ValueError('Placeholder must be nonempty')

    def resolve_overlaps(self,findings):
        converted=[]
        for f in findings:
            if type(f.start) is not int or type(f.end) is not int or f.start<0 or f.start>=f.end:
                raise ValueError('Invalid redaction offset')
            if not isinstance(f.confidence,(int,float)) or not math.isfinite(f.confidence) or not 0<=f.confidence<=1:
                raise ValueError('Invalid finding confidence')
            if not isinstance(f.entity_type,str) or not f.entity_type.replace('_','').isalnum():
                raise ValueError('Invalid entity type')
            converted.append(Finding(f.document_id,f.block_id,f.entity_type,f.start,f.end,f.confidence,f.detector,getattr(f,'source_location','')))
        merged=[]
        for f in sorted(converted,key=lambda f:(f.document_id,f.block_id,f.start,-f.end,-f.confidence,f.entity_type)):
            if merged and (f.document_id,f.block_id)==(merged[-1].document_id,merged[-1].block_id) and f.start<merged[-1].end:
                old=merged[-1]
                primary=min([old,f],key=lambda x:(-(x.end-x.start),-x.confidence,x.entity_type))
                merged[-1]=replace(primary,start=min(old.start,f.start),end=max(old.end,f.end))
            else: merged.append(f)
        return merged

    def redact_block(self,block,findings,token_registry,entity_counters):
        selected=[f for f in findings if f.block_id==block.block_id and f.document_id==block.document_id]
        if any(type(f.end) is not int or f.end>len(block.text) for f in selected):
            raise ValueError('Finding exceeds original block text')
        resolved=self.resolve_overlaps(selected); text=block.text
        for f in reversed(resolved):
            original=block.text[f.start:f.end]
            kind=f.entity_type.upper(); normalized=original.casefold().strip()
            registry=token_registry.setdefault(kind,{})
            if normalized not in registry:
                entity_counters[kind]=entity_counters.get(kind,0)+1
                registry[normalized]=self.token_format.format(entity_type=kind,index=entity_counters[kind])
            text=text[:f.start]+registry[normalized]+text[f.end:]
        return text,resolved

    def redact_document(self,blocks,findings):
        blocks=list(blocks); findings=list(findings)
        keys={(b.document_id,b.block_id) for b in blocks}
        if len(keys)!=len(blocks) or len({b.document_id for b in blocks})>1:
            raise ValueError('Redact one document with unique block identities')
        if any((f.document_id,f.block_id) not in keys for f in findings):
            raise ValueError('Finding references an unknown block/document')
        registry=defaultdict(dict); counters=defaultdict(int); counts=defaultdict(int); output=[]
        for b in blocks:
            text,applied=self.redact_block(b,findings,registry,counters)
            for f in applied: counts[f.entity_type]+=1
            confidence=getattr(b,'OCR_confidence',None)
            if confidence is None and getattr(b,'ocr_confidence',None) is not None: confidence=b.ocr_confidence/100
            output.append(Block(b.document_id,b.block_id,b.page_or_slide,b.source_kind,b.reading_order,text,
                                getattr(b,'table_row',None),getattr(b,'table_column',None),getattr(b,'bbox',None),
                                confidence,getattr(b,'extraction_complete',False)))
        mapping={value:token for values in registry.values() for value,token in values.items()}
        return output,mapping,dict(counts)
