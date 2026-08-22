#!/usr/bin/env python3
"""Self-check for add-checksums.py: python3 scripts/test_add_checksums.py

Covers the part that produced a false alarm: a download cut short used to be
hashed as if complete and reported as a checksum MISMATCH, which is the one
message that should mean "this is not the file we pinned".
"""
import hashlib
import http.server
import importlib.util
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("addsums", HERE / "add-checksums.py")
addsums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addsums)

BODY = b"x" * 5000
FULL_SHA = hashlib.sha256(BODY).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    mode = "full"
    attempts = 0

    def do_GET(self):
        Handler.attempts += 1
        if Handler.mode == "truncate":
            # Declares the full length, sends less -- a connection dropped
            # mid-transfer looks exactly like this.
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY[:100])
        elif Handler.mode == "flaky" and Handler.attempts < 3:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/f.tar.gz"


def main():
    srv, url = serve()
    addsums.ATTEMPTS = 3

    Handler.mode, Handler.attempts = "full", 0
    assert addsums.sha256_url(url) == FULL_SHA, "a complete download must hash to itself"

    # The load-bearing case: truncated must NOT come back as a hash.
    Handler.mode, Handler.attempts = "truncate", 0
    try:
        got = addsums.sha256_url(url)
    except addsums.Unreachable as e:
        assert "truncated" in str(e), f"unhelpful message: {e}"
    else:
        print(f"FAIL: truncated download returned a digest ({got}) instead of raising")
        return 1

    # A transient failure must not be permanent: two 500s then success.
    Handler.mode, Handler.attempts = "flaky", 0
    assert addsums.sha256_url(url) == FULL_SHA, "must retry past a transient failure"

    srv.shutdown()
    print("add-checksums self-check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
