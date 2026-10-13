"""Real adapter, recognizer, release and upload regressions added during integration."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import bootstrap
import dataclasses
import io
import json
import math
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import http.client
from cadence_detection.detection.comprehensive import ComprehensiveDetector,luhn,valid_birth_date
from cadence_detection.detection.pii_detector import Block as DBlock,Finding as DFinding
from cadence_detection.redaction.models import Block,Finding
from cadence_detection.redaction.redactor import TextRedactor
from cadence_detection.redaction.gate import SafeReleaseGate
from cadence_detection.runtime import process_document,run_for_qa
from cadence_detection.web import LocalServer
from cadence_detection.extraction.models import ExtractionOptions
from cadence_detection.extraction.ocr import OCRLine
from build_qa_fixture import make_fixture
from cadence_detection.evaluation import evaluate_bundle


class DetectorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.detector=ComprehensiveDetector()

    def test_supplied_synthetic_actual_text_detector(self):
        b=make_fixture()
        b['predictions']=[dataclasses.asdict(f) for f in self.detector.detect_blocks([DBlock(x['document_id'],x['block_id'],x['text']) for x in b['blocks']])]
        b['results']=[];b['structure_reviews']=[]
        score=evaluate_bundle(b)['exact_text']
        self.assertEqual((score['tp'],score['fp'],score['fn']),(18,0,0))

    def test_all_text_categories(self):
        cases={
          'PERSON':'Name: Imani Example', 'EMAIL':'Email: person@example.invalid.', 'PHONE':'+1 (555) 0114',
          'EMPLOYEE_ID':'EMP-38104', 'DIRECTOR_ID':'DIR-0042', 'VENDOR_PERSON_ID':'MER-IN-4471',
          'DATE_OF_BIRTH':'Born 14 May 1990', 'HOME_ADDRESS':'Home address: 18 Willowbank Court, Hoboken',
          'NATIONAL_ID':'SSN: 000-12-3456', 'TAX_ID':'PAN: ABCDE1234F', 'PASSPORT':'Passport: QX3817290',
          'BANK_ACCOUNT':'Account number: ACC-123456789', 'PAYMENT_CARD':'4111 1111 1111 1111',
          'PARTIAL_IDENTIFIER':'last four digits: 8827'}
        for kind,text in cases.items():
            with self.subTest(kind=kind):self.assertIn(kind,{f.entity_type for f in self.detector.detect_blocks([DBlock('d','b',text)])})

    def test_business_negative_context(self):
        text='OneTrust and Ironclad support Tier 2 reviews every 24 months. Policy GRP-POL-001, DDQ-004, USD 2.4m and 11 March 2026 are business context.'
        self.assertEqual(self.detector.detect_blocks([DBlock('d','b',text)]),[])

    def test_workflow_labels_are_not_people(self):
        labels=['Full Admin','Edit Access','Due Diligence Questionnaire','Create Risk','Default Onboarding Workflow','Assessment Submitted','Tier 1']
        for label in labels:
            with self.subTest(label=label):self.assertEqual(self.detector.detect_blocks([DBlock('d','b',label)]),[])

    def test_unicode_and_repeated_aliases(self):
        text="Name: Zoë Example. Zoë Example and Z. Example attended."
        findings=self.detector.detect_blocks([DBlock('d','b',text)])
        people=[text[f.start:f.end] for f in findings if f.entity_type=='PERSON']
        self.assertEqual(people.count('Zoë Example'),2);self.assertIn('Z. Example',people)

    def test_dob_validation(self):
        self.assertTrue(valid_birth_date('29 February 2000'))
        for value in ['31 February 1990','1990-13-14','30/02/1991','2099-01-01']:
            with self.subTest(value=value):self.assertFalse(valid_birth_date(value))

    def test_luhn_validation(self):
        self.assertTrue(luhn('4111 1111 1111 1111'));self.assertFalse(luhn('4111 1111 1111 1112'));self.assertFalse(luhn('1234'))

    def test_exact_unicode_offsets_and_no_mutation(self):
        text='🙂 Name: Zoë Example. Email: zoe@example.invalid.'
        findings=self.detector.detect_blocks([DBlock('d','b',text)])
        for f in findings:self.assertEqual(text[f.start:f.end],text[f.start:f.end].strip())
        out,_,_=TextRedactor().redact_document([Block('d','b',1,'paragraph',0,text)],findings)
        self.assertTrue(out[0].text.startswith('🙂 '));self.assertNotIn('zoe@example.invalid',out[0].text)


class ReleaseRegressionTests(unittest.TestCase):
    def block(self,text='ABCDEFGHIJ',**kwargs):return Block('d','b',1,'paragraph',0,text,**kwargs)
    def finding(self,start,end,**kwargs):return Finding('d','b','PERSON',start,end,.95,'test',**kwargs)

    def test_crossing_overlap_covers_union(self):
        out,_,_=TextRedactor().redact_document([self.block()],[self.finding(0,5),self.finding(3,10)])
        self.assertEqual(out[0].text,'[PERSON_1]')

    def test_transitive_overlap_union(self):
        out,_,_=TextRedactor().redact_document([self.block()],[self.finding(0,4),self.finding(3,7),self.finding(6,10)])
        self.assertEqual(out[0].text,'[PERSON_1]')

    def test_invalid_offsets_fail_closed(self):
        for start,end in [(0,999),(-1,2),(2,2),(4,3),(True,4),(0,1.5)]:
            with self.subTest(span=(start,end)),self.assertRaises(ValueError):
                TextRedactor().redact_document([self.block()],[self.finding(start,end)])

    def test_frozen_detector_finding_is_supported(self):
        f=DFinding('d','b','PERSON',0,10,.95,'test','test')
        out,_,_=TextRedactor().redact_document([self.block()],[f])
        self.assertEqual(out[0].text,'[PERSON_1]');self.assertFalse(hasattr(f,'original_text'))

    def test_unknown_finding_fails_closed(self):
        f=Finding('other','b','PERSON',0,3,.9,'test')
        with self.assertRaises(ValueError):TextRedactor().redact_document([self.block()],[f])

    def test_multiple_documents_rejected(self):
        with self.assertRaises(ValueError):TextRedactor().redact_document([self.block(),Block('other','x',1,'paragraph',0,'Text')],[])

    def test_invalid_confidence(self):
        for value in [float('nan'),float('inf'),-1,2]:
            f=self.finding(0,3);f.confidence=value
            with self.subTest(value=value),self.assertRaises(ValueError):TextRedactor().redact_document([self.block()],[f])

    def test_gate_catches_previously_missed_categories(self):
        for text in ['Customer Noor Example attended.','DOB: 1990-05-14','Born 14 May 1990','PAN: ABCDE1234F','Passport: QX3817290']:
            with self.subTest(case=text):self.assertEqual(SafeReleaseGate().evaluate([self.block(text)]).status,'QUARANTINED')

    def test_original_span_verification(self):
        original=self.block('SecretABC')
        f=self.finding(0,9)
        result=SafeReleaseGate().evaluate([original],original_blocks=[original],expected_findings=[f])
        self.assertEqual(result.status,'QUARANTINED')

    def test_failure_and_quality_states(self):
        self.assertEqual(SafeReleaseGate().evaluate([]).status,'FAILED')
        for block in [self.block('ordinary context',extraction_complete=False),self.block('ordinary context',OCR_confidence=.2),self.block('ordinary context',OCR_confidence=float('nan'))]:
            self.assertEqual(SafeReleaseGate().evaluate([block]).status,'QUARANTINED')

    def test_residual_reports_never_contain_original_value(self):
        r=SafeReleaseGate().evaluate([self.block('person@example.invalid')])
        self.assertNotIn('person@example.invalid',json.dumps(dataclasses.asdict(r)))
        self.assertNotIn('matched_text',json.dumps(dataclasses.asdict(r)))

    def test_missing_ner_blocks_release(self):
        with patch.object(ComprehensiveDetector,'_nlp',None),patch.object(ComprehensiveDetector,'_attempted',True):
            self.assertEqual(SafeReleaseGate(require_ner=True).evaluate([self.block('ordinary context')]).status,'QUARANTINED')

    def test_pdf_timestamp_is_not_phone(self):
        self.assertEqual(SafeReleaseGate().evaluate([self.block("D:20261014001200+05'30'")]).status,'APPROVED')


class RealPipelineTests(unittest.TestCase):
    def test_all_twelve_file_cases(self):
        from cadence_detection.evaluation.pipeline_checks import check_case
        root=Path(__file__).resolve().parents[2]
        cases=json.loads((root/'data/synthetic/pipeline_cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(case=case['case_id']):
                result=check_case(case,run_for_qa,root/'data/synthetic/pipeline_inputs')
                self.assertEqual(result['status'],'passed',result['reasons'])

    def test_bytes_upload_and_restricted_metadata(self):
        path=Path(__file__).resolve().parents[2]/'data/synthetic/pipeline_inputs/valid.docx'
        response,ctx=process_document(path.read_bytes(),filename='../../valid.docx')
        self.assertEqual(response.release_decision.value,'safe_for_llm')
        report=json.dumps(response.to_dict())
        for literal in ['Noor Example','noor@example.invalid','token_mapping','"words"']:
            self.assertNotIn(literal,report)
        self.assertEqual(response.filename,'valid.docx')

    def test_model_absence_blocks_pipeline(self):
        path=Path(__file__).resolve().parents[2]/'data/synthetic/pipeline_inputs/valid.pdf'
        with patch.object(ComprehensiveDetector,'_nlp',None),patch.object(ComprehensiveDetector,'_attempted',True):
            response,ctx=process_document(path)
        self.assertEqual(response.release_decision.value,'not_safe_for_llm');self.assertIsNone(response.sanitized_text)


class UploadServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=LocalServer(('127.0.0.1',0));cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def request(self,path,data=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=60)
        connection.request('POST' if data is not None else 'GET',path,body=data,headers=headers or {})
        response=connection.getresponse();payload=response.read();status=response.status;connection.close()
        if status>=400:raise HTTPError(self.url+path,status,'Local HTTP error',{},io.BytesIO(payload))
        return io.BytesIO(payload)

    def test_ui_and_health(self):
        self.assertEqual(json.load(self.request('/health'))['status'],'ok')
        html=self.request('/').read().decode();self.assertIn('Evidence privacy review',html);self.assertIn(self.server.token,html)

    def test_unauthorized_and_cross_origin_rejected(self):
        for headers in [{},{'X-Cadence-Token':self.server.token,'Origin':'http://evil.invalid'}]:
            with self.subTest(headers=bool(headers)):
                with self.assertRaises(HTTPError) as caught:self.request('/api/jobs?filename=valid.pdf',b'123',headers)
                self.assertEqual(caught.exception.code,403)

    def test_actual_upload_poll_and_download(self):
        data=(Path(__file__).resolve().parents[2]/'data/synthetic/pipeline_inputs/valid.pptx').read_bytes()
        headers={'X-Cadence-Token':self.server.token,'Content-Type':'application/octet-stream'}
        jid=json.load(self.request('/api/jobs?filename=valid.pptx',data,headers))['job_id']
        for _ in range(100):
            job=json.load(self.request('/api/jobs/'+jid,headers=headers))
            if job['state'] in ('finished','failed'):break
            time.sleep(.1)
        self.assertEqual(job['state'],'finished');self.assertEqual(job['result']['release_decision'],'safe_for_llm')
        text=self.request('/api/jobs/'+jid+'/download',headers=headers).read().decode()
        self.assertNotIn('Noor Example',text);self.assertNotIn('noor@example.invalid',text)
        self.assertNotIn('original',job)

    def test_failed_document_download_is_blocked(self):
        headers={'X-Cadence-Token':self.server.token}
        jid=json.load(self.request('/api/jobs?filename=corrupt.pdf',b'invalid',headers))['job_id']
        for _ in range(50):
            job=json.load(self.request('/api/jobs/'+jid,headers=headers))
            if job['state']=='finished':break
            time.sleep(.05)
        with self.assertRaises(HTTPError) as caught:self.request('/api/jobs/'+jid+'/download',headers=headers)
        self.assertEqual(caught.exception.code,403)


if __name__=='__main__':unittest.main()
