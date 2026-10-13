"""Locate optional project-local dependencies and bundled local runtimes."""
from pathlib import Path
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
for name in ['nlp-runtime']:
    path=ROOT/'.local'/name
    if path.exists(): sys.path.insert(0,str(path))
runtime=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'
node=runtime/'node/bin/node.exe'; module=runtime/'node/node_modules/tesseract.js'
if node.exists() and module.exists() and (ROOT/'.local/ocr/eng.traineddata').exists():
    os.environ.setdefault('CADENCE_NODE',str(node)); os.environ.setdefault('CADENCE_TESSERACT_JS',str(module)); os.environ.setdefault('CADENCE_TESSDATA',str(ROOT/'.local/ocr'))
temporary=ROOT/'tmp/runtime'; temporary.mkdir(parents=True,exist_ok=True)
os.environ['TMP']=str(temporary); os.environ['TEMP']=str(temporary)
