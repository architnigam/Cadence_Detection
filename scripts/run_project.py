"""Run real validation -> extraction -> detection -> redaction -> verification."""
import bootstrap
import argparse
import json
from pathlib import Path
from cadence_detection.runtime import process_document
from cadence_detection.extraction import ExtractionOptions

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',type=Path)
    parser.add_argument('--output-dir',type=Path,default=Path('output/reports/runs'))
    parser.add_argument('--regions',type=Path)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    failed=False
    for path in args.files:
        regions={int(k):v for k,v in json.loads(args.regions.read_text()).items()} if args.regions and path.suffix.lower()=='.pdf' else {}
        response,ctx=process_document(path,options=ExtractionOptions(ocr_regions=regions),progress=lambda stage:print(stage,flush=True))
        out=args.output_dir/(response.document_id+'.json')
        out.write_text(json.dumps(response.to_dict(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if response.sanitized_text is not None:
            out.with_suffix('.txt').write_text(response.sanitized_text,encoding='utf-8')
        print(json.dumps({'document_id':response.document_id,'status':response.status.value,'release':response.release_decision.value,'counts':response.summary}),flush=True)
        failed=failed or response.sanitized_text is None
    return 2 if failed else 0

if __name__=='__main__': raise SystemExit(main())
