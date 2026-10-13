"""Compatibility entry point for the real local upload application."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from cadence_detection.web import serve

if __name__ == "__main__": serve()
