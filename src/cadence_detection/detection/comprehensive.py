"""Local document-level recognizers. Scores are heuristic, not probabilities.

Rules are format-independent and never depend on evaluation gold. Optional local
spaCy NER improves names in narrative prose; absence is reported by the pipeline.
"""
from __future__ import annotations

import calendar
from datetime import date
import re
import threading
from .pii_detector import Finding

EMAIL = re.compile(r"(?<![\w.@])[A-Za-z0-9_%+.-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?![\w@])")
NAME_TOKEN = r"(?:[A-ZÀ-ÖØ-Þ][\w'’\-]+|[A-Z]\.)"
NAME = re.compile(rf"(?<!\w){NAME_TOKEN}(?:[ \t]+{NAME_TOKEN}){{1,3}}(?!\w)")
MONTHS = {m.lower(): i for i,m in enumerate(calendar.month_name) if m}
MONTH_PATTERN = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = re.compile(rf"\b(?:\d{{1,2}}[ \t]+{MONTH_PATTERN}[ \t]+\d{{4}}|{MONTH_PATTERN}[ \t]+\d{{1,2}},?[ \t]+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{4}})\b", re.I)
PHONE = re.compile(r"(?<![\w])(?:\+\d{1,3}[ \t.-]*(?:\(\d{2,4}\)[ \t.-]*)?\d(?:[ \t()./-]*\d){2,13}|\(\d{3}\)[ \t.-]*\d{3}[ \t.-]*\d{4}|\d{3}[-.]\d{3}[-.]\d{4})(?!\w)")
CONTEXT_PHONE = re.compile(r"(?i)\b(?:phone|telephone|tel|mobile|cell|fax|contact|extension|ext)\b[ \t]*(?:number|no\.?)?[ \t]*[:#-]?[ \t]*(\+?\(?\d(?:[ \t()./-]*\d){2,14})")
IDS = [
    ('EMPLOYEE_ID', re.compile(r"\bEMP-(?:[A-Z]+-)?\d{3,8}\b")),
    ('DIRECTOR_ID', re.compile(r"\bDIR-(?:[A-Z]+-)?\d{3,8}\b")),
    ('VENDOR_PERSON_ID', re.compile(r"\b(?:VENDOR-PERSON-\d+|VEND-\d+|MER-[A-Z]{2}-\d+|MER-(?:IN|PL)-\d+)\b")),
    ('NATIONAL_ID', re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ('TAX_ID', re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ('PASSPORT', re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
]
LABEL_TYPES = {
    'employee id':'EMPLOYEE_ID', 'director id':'DIRECTOR_ID', 'vendor person id':'VENDOR_PERSON_ID',
    'national id':'NATIONAL_ID', 'ssn':'NATIONAL_ID', 'aadhaar':'NATIONAL_ID', 'pesel':'NATIONAL_ID',
    'tax id':'TAX_ID', 'tin':'TAX_ID', 'pan':'TAX_ID', 'passport':'PASSPORT',
    'bank account':'BANK_ACCOUNT', 'account number':'BANK_ACCOUNT', 'acct':'BANK_ACCOUNT',
    'payment card':'PAYMENT_CARD', 'card number':'PAYMENT_CARD',
    'partial identifier':'PARTIAL_IDENTIFIER',
}
LABEL_PATTERNS = [(key, kind, re.compile(r'(?i)(?<!\w)'+re.escape(key).replace(r'\ ',r'[ _]')+r'[ \t]*(?:number|no\.?)?[ \t]*[:#-]?[ \t]+([A-Z0-9][A-Z0-9*Xx -]{2,35})(?!\w)')) for key,kind in LABEL_TYPES.items()]
BUSINESS_WORDS = set('Risk Management Group Financial Cadence Financial Group OneTrust Ironclad Privacy Review Chief Executive Officer General Counsel Data Protection Information Security Technology Operations Finance People Culture Director Compliance Committee Board Enterprise Policy Training Organizational Pack Version Document Control Tier Service Level Agreement Internal Assurance United States New York London Page Confidential Name Employee Mobile Email Role Division Contact Customer Record Home Address Date Birth Reviewer Account Number Payment Card National Tax Passport Identity Appendix'.split())
BUSINESS_WORDS.update('Full Admin Edit Access Create Configure Questionnaire Due Diligence Template Workflow Vendor Third Party Parties Legal Procurement Marketing Revenue International Staffing Standard Renewal Offboarding Assessment Rules Rule Condition Trigger Response Action Approve Approved Reject Rejected Task Stage Details Section Description Type Users User Team View Save Publish New Onboarding Completed Submitted Read Only General Country Certification Background Breach Notification Retention Encryption Required Optional Attribute Values Value Submit Scoring Score Default Schedule SLA Question Questions Reminder System And To For Of In From With'.split())
BUSINESS_WORDS={word.casefold() for word in BUSINESS_WORDS}
PERSON_CONTEXT = re.compile(r'(?i)\b(?:name|employee|customer|reviewer|officer|manager|owner|assignee|author|prepared by|approved by|accepted by|dear|led by|contact)\s*[:=-]?\s*$')


def luhn(value):
    digits=[int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total=0
    for i,n in enumerate(reversed(digits)):
        if i%2: n=n*2-9 if n*2>9 else n*2
        total+=n
    return total%10==0


def valid_birth_date(value):
    numbers = re.findall(r'\d+',value)
    try:
        if re.search(r'[A-Za-z]', value):
            month=next(MONTHS[m.lower()] for m in re.findall(r'[A-Za-z]+',value) if m.lower() in MONTHS)
            day,year=map(int,numbers)
            parsed=date(year,month,day)
        else:
            a,b,c=map(int,numbers)
            if a>999: parsed=date(a,b,c)
            else:
                try: parsed=date(c,b,a)
                except ValueError: parsed=date(c,a,b)
        return 1900 <= parsed.year and parsed<=date.today()
    except (ValueError,StopIteration):
        return False


class ComprehensiveDetector:
    _nlp = None
    _attempted = False
    _lock = threading.RLock()

    def __init__(self, use_ner=True):
        self.use_ner=use_ner
        if use_ner:
            with self._lock:
                if not type(self)._attempted:
                    type(self)._attempted=True
                    try:
                        import en_core_web_sm
                        type(self)._nlp=en_core_web_sm.load(disable=['parser','tagger','lemmatizer','attribute_ruler'])
                    except (ImportError,OSError):
                        type(self)._nlp=None

    @property
    def ner_available(self):
        return self.use_ner and self._nlp is not None

    def detect_blocks(self, blocks):
        blocks=list(blocks)
        ner_entities=[[] for _ in blocks]
        if self.ner_available:
            with self._lock:
                for i,doc in enumerate(self._nlp.pipe((str(b.text) for b in blocks),batch_size=64)):
                    ner_entities[i]=[(e.start_char,e.end_char) for e in doc.ents if e.label_=='PERSON']
        lexicon=set()
        for i,b in enumerate(blocks):
            for start,end in ner_entities[i]:
                value=b.text[start:end].strip()
                if self._plausible_name(value): lexicon.add(value)
            for match in NAME.finditer(b.text):
                value=match.group()
                prefix=b.text[max(0,match.start()-45):match.start()]
                if self._plausible_name(value) and (PERSON_CONTEXT.search(prefix) or b.text.strip()==value or re.match(r'\s+(?:is|uses|was|chairs|reports|attended)\b',b.text[match.end():])):
                    lexicon.add(value)
            contextual=re.compile(rf'(?i:\b(?:employee name|name|customer|reviewer|dear|officer|manager|owner|assignee|author|led by))\s*[:=-]?\s+({NAME_TOKEN}(?:[ \t]+{NAME_TOKEN}){{1,3}})')
            for match in contextual.finditer(b.text):
                if self._plausible_name(match.group(1)): lexicon.add(match.group(1))
        # A document-local name directory also covers abbreviated RACI references.
        aliases=set(lexicon)
        for name in lexicon:
            parts=name.split()
            if len(parts)>1:
                aliases.add(parts[0][0]+'. '+' '.join(parts[1:]))
                if len(parts)>2: aliases.add(' '.join(p[0]+'.' for p in parts[:-1])+' '+parts[-1])
        out=[]
        for i,b in enumerate(blocks):
            previous=blocks[i-1].text if i else ''
            out.extend(self._detect(b,aliases,ner_entities[i],previous))
        # Keep overlapping coverage: the redactor unions spans instead of dropping coverage.
        seen=set(); unique=[]
        for f in sorted(out,key=lambda f:(f.document_id,f.block_id,f.start,-f.end,f.entity_type)):
            key=(f.document_id,f.block_id,f.entity_type,f.start,f.end)
            if key not in seen: seen.add(key); unique.append(f)
        return unique

    @staticmethod
    def _plausible_name(value):
        parts=value.split()
        return (2<=len(parts)<=4 and not any(p.strip('.').isdigit() for p in parts)
                and not any(p.strip('.,').casefold() in BUSINESS_WORDS for p in parts)
                and not any(c in value for c in '@/:;_') and not any(c.isdigit() for c in value)
                and all(any(c.isalpha() for c in p) and (p[0].isupper() or p in {'de','van','von','da','del'}) for p in parts))

    def _detect(self,b,aliases,ner,previous):
        text=b.text; found=[]
        def add(kind,start,end,confidence=.95):
            if 0<=start<end<=len(text):
                found.append(Finding(b.document_id,b.block_id,kind,start,end,confidence,'cadence.local.v1',getattr(b,'source_location',f'{b.block_id}:{start}:{end}')))
        for m in EMAIL.finditer(text): add('EMAIL',*m.span())
        for kind,pattern in IDS:
            for m in pattern.finditer(text): add(kind,*m.span())
        for m in PHONE.finditer(text):
            if 7 <= sum(c.isdigit() for c in m.group()) <= 15 and not re.fullmatch(r'\d{3}-\d{2}-\d{4}',m.group()): add('PHONE',*m.span(),.92)
        for m in CONTEXT_PHONE.finditer(text):
            value=m.group(1)
            if sum(c.isdigit() for c in value)>=7 and not DATE.fullmatch(value): add('PHONE',*m.span(1),.92)
        for _,kind,pattern in LABEL_PATTERNS:
            for m in pattern.finditer(text):
                value=m.group(1).rstrip(); end=m.start(1)+len(value)
                # Stop before the next English label; numeric/identifier tokens remain local.
                if any(c.isdigit() for c in value):
                    token=re.match(r'[A-Z0-9*Xx]+(?:[- ][A-Z0-9*Xx]+)*',value)
                    if token: add(kind,m.start(1),m.start(1)+len(token.group()),.92)
        for m in DATE.finditer(text):
            context=text[max(0,m.start()-65):m.start()]
            if m.start()==0 and re.fullmatch(r'(?i)\s*(?:dob|date of birth|birth date)\s*:?\s*',previous): context=previous
            if re.search(r'(?i)\b(?:dob|date[ _]of[ _]birth|birth[ _]date|born)\b',context) and valid_birth_date(m.group()): add('DATE_OF_BIRTH',*m.span())
        for m in re.finditer(r'\b\d(?:[ -]?\d){12,18}\b',text):
            if luhn(m.group()): add('PAYMENT_CARD',*m.span())
        for m in re.finditer(r'(?i)\b(?:home[ _]address|residential address|resides at|lives at)\s*[:=-]?\s*([^;\n]+)',text):
            add('HOME_ADDRESS',*m.span(1),.92)
        address=re.compile(r'\b\d{1,6}[ \t]+(?:[\w.-]+[ \t]+){1,5}(?:Street|St|Road|Rd|Lane|Ln|Court|Ct|Drive|Dr|Avenue|Ave|Way|Boulevard)\b(?:,[ \t]*[A-Z][A-Za-z -]+(?:,[ \t]*[A-Z]{2}[ \t]+\d{5})?)?',re.I)
        for m in address.finditer(text): add('HOME_ADDRESS',*m.span(),.88)
        for m in re.finditer(r'(?i)\b(?:last four(?: digits)?|ending(?: in)?|partial[ _]identifier|SSN(?: suffix)?)\s*[:#-]?\s*(\d{4})\b',text): add('PARTIAL_IDENTIFIER',*m.span(1))
        for m in re.finditer(r'(?<!\w)(?:[A-Z0-9]*[xX*]{2,}[A-Z0-9xX*]*\d|\d[A-Z0-9]*[xX*]{2,})(?!\w)',text): add('PARTIAL_IDENTIFIER',*m.span(),.9)
        for alias in sorted(aliases,key=len,reverse=True):
            for m in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text): add('PERSON',*m.span(),.9)
        for start,end in ner:
            if self._plausible_name(text[start:end]): add('PERSON',start,end,.88)
        return found
