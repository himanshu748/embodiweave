"""Forward the former Render website to the current deployment, without using model credentials."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CANONICAL = 'https://embodiweave.52.202.25.181.sslip.io'


class Redirect(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?', 1)[0] == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(json.dumps({'moved_to': CANONICAL}).encode())
            return
        self.send_response(302)
        self.send_header('Location', CANONICAL + '/' + self.path.lstrip('/'))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8000))), Redirect).serve_forever()
