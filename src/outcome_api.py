"""
Sprint 1: HTTP endpoint for recording outcomes.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
from outcome_store import OutcomeStore

store = OutcomeStore()

class OutcomeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/outcome":
            self.send_response(404)
            self.end_headers()
            return
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
            required = ['transaction_id', 'label', 'value']
            if not all(k in data for k in required):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "missing required fields"}')
                return
            
            store.record_outcome(
                data['transaction_id'],
                data['label'],
                data['value'],
                data.get('metadata')
            )
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "recorded"}')
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "invalid json"}')
    
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/outcome":
            params = parse_qs(parsed.query)
            tx_id = params.get('transaction_id', [None])[0]
            label = params.get('label', [None])[0]
            if not tx_id or not label:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "transaction_id and label required"}')
                return
            
            value = store.get_outcome(tx_id, label)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"transaction_id": tx_id, "label": label, "value": value}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8080):
    server = HTTPServer(('localhost', port), OutcomeHandler)
    print(f"Outcome API running on http://localhost:{port}")
    print("POST /outcome - record outcome")
    print("GET /outcome?transaction_id=...&label=... - retrieve outcome")
    server.serve_forever()

if __name__ == "__main__":
    run_server()

