import http.server, os, sys, json
ROOT = sys.argv[1]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
    def do_GET(s):
        path = s.path.split('?')[0]
        if path.startswith('/api/'):
            b = json.dumps({"clientId": ""}).encode(); s.send_response(200); s.send_header('Content-Type','application/json'); s.end_headers(); s.wfile.write(b); return
        fp = os.path.join(ROOT, path.lstrip('/'))
        if os.path.isdir(fp) and not path.endswith('/'):
            s.send_response(307); s.send_header('Location', path + '/'); s.end_headers(); return
        if os.path.exists(fp if not os.path.isdir(fp) else os.path.join(fp,'index.html')): return super().do_GET()
        b = open(os.path.join(ROOT,'404.html'),'rb').read(); s.send_response(404); s.send_header('Content-Type','text/html'); s.end_headers(); s.wfile.write(b)
http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[2])), H).serve_forever()
