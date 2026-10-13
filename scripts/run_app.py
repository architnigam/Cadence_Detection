"""Launch the actual local upload application."""
import bootstrap
import argparse
from cadence_detection.web import serve

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8501)
    args=p.parse_args();serve(port=args.port)
