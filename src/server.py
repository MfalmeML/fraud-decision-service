"""
Complete decision service HTTP server.
Integrates decision engine, reliability, and outcome recording.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
from src.decision_engine import DecisionEngine
from src.reliability import ThresholdTableManager
from src.outcome_store import OutcomeStore
from src.threshold_optimizer import ThresholdOptimizer

class DecisionServer:
    def __init__(self):
        self.engine = DecisionEngine()
        self.manager = ThresholdTableManager()
        self.store = OutcomeStore()
        self.optimizer = ThresholdOptimizer()
    
    def decide(self, payload: dict) -> dict:
        """Execute decision with reliability layer."""
        segment = payload.get('segment', {})
        score = payload.get('combined_risk_score', 0.5)
        ring_score = payload.get('ring_score', 0.0)
        confirmed = payload.get('confirmed_members', 0)
        
        # Check if table is stale
        if self.manager.is_stale():
            self.manager.fallback_to_lkg()
        
        # Get thresholds from reliability layer
        seg_key = f"{segment.get('customer_tier', 'established')}|{segment.get('geography', 'domestic')}"
        t_ch, t_de = self.manager.lookup(seg_key)
        
        # Use engine with current thresholds
        result = self.engine.decide(score, segment, ring_score, confirmed)
        result['threshold_table_version'] = self.manager.get_version()
        
        return result
    
    def record_outcome(self, payload: dict) -> dict:
        """Record outcome label for a transaction."""
        required = ['transaction_id', 'label', 'value']
        if not all(k in payload for k in required):
            return {'error': 'missing required fields'}
        
        self.store.record_outcome(
            payload['transaction_id'],
            payload['label'],
            payload['value'],
            payload.get('metadata')
        )
        return {'status': 'recorded'}
    
    def publish_table(self, payload: dict) -> dict:
        """Publish new threshold table with canary validation."""
        table = payload.get('table')
        version = payload.get('version')
        if not table or not version:
            return {'error': 'table and version required'}
        
        success = self.manager.publish_table(
            table,
            version,
            'data/sample_outcomes.json',
            payload.get('fraud_ceiling', 1000.0)
        )
        return {'success': success, 'version': version if success else None}
    
    def get_thresholds(self, segment_key: str) -> dict:
        """Get current thresholds for a segment."""
        t_ch, t_de = self.manager.lookup(segment_key)
        return {
            'segment_key': segment_key,
            't_challenge': t_ch,
            't_decline': t_de,
            'version': self.manager.get_version()
        }

class DecisionHandler(BaseHTTPRequestHandler):
    server_instance = None
    
    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {'error': 'invalid json'})
            return
        
        handler = self.server_instance
        
        if parsed.path == '/decide':
            result = handler.decide(data)
            self._send_json(200, result)
        elif parsed.path == '/outcome':
            result = handler.record_outcome(data)
            self._send_json(200, result)
        elif parsed.path == '/publish':
            result = handler.publish_table(data)
            self._send_json(200, result)
        else:
            self._send_json(404, {'error': 'not found'})
    
    def do_GET(self):
        parsed = urlparse(self.path)
        handler = self.server_instance
        
        if parsed.path == '/health':
            self._send_json(200, {'status': 'ok', 'version': handler.manager.get_version()})
        elif parsed.path.startswith('/thresholds/'):
            seg_key = parsed.path.split('/thresholds/')[1]
            result = handler.get_thresholds(seg_key)
            self._send_json(200, result)
        elif parsed.path.startswith('/outcome'):
            params = parse_qs(parsed.query)
            tx_id = params.get('transaction_id', [None])[0]
            label = params.get('label', [None])[0]
            if not tx_id or not label:
                self._send_json(400, {'error': 'transaction_id and label required'})
                return
            value = handler.store.get_outcome(tx_id, label)
            self._send_json(200, {'transaction_id': tx_id, 'label': label, 'value': value})
        else:
            self._send_json(404, {'error': 'not found'})
    
    def _send_json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def main():
    server = HTTPServer(('localhost', 8080), DecisionHandler)
    DecisionHandler.server_instance = DecisionServer()
    print("Fraud Decision Service running on http://localhost:8080")
    print("Endpoints:")
    print("  POST /decide       - make decision")
    print("  POST /outcome      - record outcome")
    print("  POST /publish      - publish threshold table")
    print("  GET  /health       - health check")
    print("  GET  /thresholds/{segment_key} - get thresholds")
    print("  GET  /outcome?transaction_id=&label= - get outcome")
    server.serve_forever()

if __name__ == '__main__':
    main()