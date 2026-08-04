"""Minimal OpenAI-compatible mock server for manual testing without real API
keys. Not part of the app; run standalone:

    python3 worker/tests/mock_openai_server.py [port]

Serves deterministic fake embeddings (hash-based) and a canned streamed chat
reply, just enough to exercise OpenAIEmbedder/OpenAILLM's HTTP/parsing code.
"""

import hashlib
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def fake_embedding(text: str, dim: int = 8) -> list[float]:
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    return [(seed[i % len(seed)] - 128) / 128 for i in range(dim)]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path.endswith("/embeddings"):
            inputs = body.get("input", [])
            data = [{"index": i, "embedding": fake_embedding(t)} for i, t in enumerate(inputs)]
            self._send_json({"data": data})
            return

        if self.path.endswith("/chat/completions"):
            self._stream_chat(body)
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def _stream_chat(self, body):
        question = body.get("messages", [{}])[-1].get("content", "")
        reply = f"（模拟回答）关于「{question[:20]}」，参考片段 [1] 中提到了相关内容。"

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for ch in reply:
            chunk = {"choices": [{"delta": {"content": ch}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.005)
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9500
    print(f"mock OpenAI-compatible server on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
