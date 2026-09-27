"""One-shot loopback receiver for the explicit browser backup UI. No cloud upload."""
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'private-handoff'
OUT.mkdir(parents=True, exist_ok=True)
TOKEN = secrets.token_urlsafe(32)
PAGE = ROOT / 'public' / 'handoff-backup.html'
PAGE.write_text('''<!doctype html><meta charset="utf-8"><title>项目私密备份</title>
<h1>项目私密备份</h1><p>导出当前网站的浏览器设置与本地录音到本机交接目录，不上传云端。</p>
<button id="export">导出浏览器项目数据</button><p id="status"></p>
<script>
document.querySelector('#export').onclick = async () => {
 const status = document.querySelector('#status'); status.textContent='正在导出…';
 try {
 const storage = {};
 for(let i=0;i<localStorage.length;i++) { const key=localStorage.key(i); if(key.startsWith('beyond-words')) storage[key]=localStorage.getItem(key); }
 const db = await new Promise((resolve,reject)=>{const r=indexedDB.open('beyond-words-audio',1);r.onupgradeneeded=()=>r.result.createObjectStore('recordings');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
 const audio = await new Promise((resolve,reject)=>{const rows=[];const r=db.transaction('recordings').objectStore('recordings').openCursor();r.onsuccess=()=>{const c=r.result;if(!c){resolve(rows);return;}rows.push({key:c.key,blob:c.value});c.continue();};r.onerror=()=>reject(r.error);}); db.close();
 const recordings=[];
 for(const row of audio){const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(r.error);r.readAsDataURL(row.blob);});recordings.push({key:row.key,type:row.blob.type,size:row.blob.size,data});}
 const response=await fetch('http://127.0.0.1:8766/TOKEN', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({origin:location.origin,exported_at:new Date().toISOString(),localStorage:storage,recordings})});
 if(!response.ok)throw new Error('本机接收失败');
 status.textContent=`导出完成：${Object.keys(storage).length} 项设置，${recordings.length} 段本地录音。`;
 }catch(error){status.textContent='导出失败：'+error.message;}
};
</script>'''.replace('TOKEN', TOKEN), encoding='utf-8')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def headers_ok(self, status):
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:5173')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.end_headers()

    def do_OPTIONS(self):
        self.headers_ok(204)

    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if self.path != '/' + TOKEN or self.headers.get('Origin') != 'http://127.0.0.1:5173' or not 0 < size <= 512 * 1024 * 1024:
            self.headers_ok(403)
            return
        data = self.rfile.read(size)
        payload = json.loads(data)
        if not isinstance(payload.get('recordings'), list):
            self.headers_ok(400)
            return
        (OUT / 'browser-snapshot.json').write_bytes(data)
        self.headers_ok(200)
        self.wfile.write(b'OK')
        self.server.done = True

server = HTTPServer(('127.0.0.1', 8766), Handler)
server.timeout = 2
server.done = False
try:
    import time
    deadline = time.monotonic() + 600
    while not server.done and time.monotonic() < deadline:
        server.handle_request()
finally:
    server.server_close()
    PAGE.unlink(missing_ok=True)
