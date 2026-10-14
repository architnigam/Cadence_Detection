"""Loopback-only upload UI. No third-party frontend runtime or external assets."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import secrets
import socketserver
import threading
import time
from urllib.parse import urlparse,parse_qs
from .runtime import process_document

ROOT=Path(__file__).resolve().parents[2]


class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    def server_bind(self):
        # Avoid platform reverse-DNS stalls for a loopback-only service.
        socketserver.TCPServer.server_bind(self)
        self.server_name='localhost'; self.server_port=self.server_address[1]

    def __init__(self,address,processor=process_document):
        if address[0] not in ('127.0.0.1','localhost'): raise ValueError('Local service must bind to loopback')
        self.token=secrets.token_urlsafe(32); self.jobs=OrderedDict(); self.lock=threading.Lock()
        self.workers=ThreadPoolExecutor(max_workers=2); self.processor=processor
        super().__init__(address,Handler)

    def process(self,jid,data,filename):
        def stage(value):
            with self.lock: self.jobs[jid]['stage']=value
        try:
            response,ctx=self.processor(data,filename=filename,progress=stage)
            with self.lock:
                self.jobs[jid].update(state='finished',stage='Finished',response=response.to_dict(),context=ctx)
        except Exception:
            with self.lock: self.jobs[jid].update(state='failed',stage='Processing failed; content was not released')

    def server_close(self):
        super().server_close(); self.workers.shutdown(wait=False,cancel_futures=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    def reply(self,value,code=200,kind='application/json; charset=utf-8',download=False):
        data=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        if download:self.send_header('Content-Disposition','attachment; filename="sanitized.txt"')
        self.end_headers();self.wfile.write(data)

    def authorized(self):
        origin=self.headers.get('Origin')
        allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        return self.valid_host() and self.headers.get('X-Cadence-Token')==self.server.token and (origin is None or origin in allowed)

    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.valid_host():return self.reply({'error':'Loopback host required'},403)
        path=urlparse(self.path)
        if path.path=='/health':return self.reply({'status':'ok','pid':os.getpid()})
        if path.path=='/':
            data=(ROOT/'app/index.html').read_text(encoding='utf-8').replace('__TOKEN__',self.server.token).encode()
            return self.reply(data,kind='text/html; charset=utf-8')
        if not self.authorized():return self.reply({'error':'Local session authorization required'},403)
        if not path.path.startswith('/api/jobs/'):return self.reply({'error':'Not found'},404)
        jid=path.path.split('/')[3]
        with self.server.lock:job=self.server.jobs.get(jid)
        if not job:return self.reply({'error':'Job expired or not found'},404)
        result=job.get('response')
        if path.path.endswith('/download'):
            if not result or result.get('release_decision')!='safe_for_llm':return self.reply({'error':'Export blocked: review required'},403)
            return self.reply(result['sanitized_text'].encode(),kind='text/plain; charset=utf-8',download=True)
        output={k:job[k] for k in ('state','stage')}
        if result:
            ctx=job['context']; output['result']=result
            output['preview']=[{'text':b.text,'page':b.page_or_slide,'kind':b.source_kind,'id':b.block_id} for b in ctx.preview]
            output['findings']=[{'type':f.entity_type,'block_id':f.block_id,'start':f.start,'end':f.end} for f in ctx.findings]
            output['issues']=[] if ctx.extraction is None else [{'code':i.code,'location':i.location} for i in ctx.extraction.issues]
            if parse_qs(path.query).get('raw')==['1']:
                output['original']=[{'text':b.text,'page':b.page_or_slide,'id':b.block_id} for b in ctx.blocks]
        return self.reply(output)

    def do_POST(self):
        if not self.authorized():
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:size=0
            if 0<size<=4096:self.rfile.read(size)
            return self.reply({'error':'Local session authorization required'},403)
        path=urlparse(self.path)
        if path.path!='/api/jobs':return self.reply({'error':'Not found'},404)
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.reply({'error':'Invalid length'},400)
        if not 0<length<=50*1024*1024:return self.reply({'error':'Choose a nonempty file up to 50 MB'},413)
        filename=parse_qs(path.query).get('filename',['upload'])[0]
        filename=Path(filename.replace('\\','/')).name[:200]
        with self.server.lock:
            for key in list(self.server.jobs):
                if self.server.jobs[key]['state'] in ('finished','failed') and time.time()-self.server.jobs[key]['created']>1200:
                    del self.server.jobs[key]
            if len(self.server.jobs)>=8:return self.reply({'error':'Session capacity reached; restart to clear local jobs'},429)
        data=self.rfile.read(length)
        if len(data)!=length:return self.reply({'error':'Incomplete upload'},400)
        jid=secrets.token_hex(16)
        with self.server.lock:self.server.jobs[jid]={'state':'running','stage':'Validating file','created':time.time()}
        self.server.workers.submit(self.server.process,jid,data,filename)
        return self.reply({'job_id':jid},202)


def serve(host='127.0.0.1',port=8501):
    server=LocalServer((host,port))
    print(f'Caddet local application: http://{host}:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
