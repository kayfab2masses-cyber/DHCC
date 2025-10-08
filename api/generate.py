# api/generate.py
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, sys

# Make sure Python can import files from the repo root:
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import your generator
import daggerheart_character_creator as dh  # assumes the function exists inside this module

def _to_json(obj):
    # generic serializer for dataclasses/objects
    try:
        return obj.__dict__
    except Exception:
        return str(obj)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        level = int(qs.get("level", ["1"])[0])
        archetype = qs.get("archetype", [None])[0]
        class_name = qs.get("class", [None])[0]
        subclass_name = qs.get("subclass", [None])[0]

        # create the character (falls back gracefully if values are None)
        char = dh.create_character(
            level=level,
            archetype=archetype,
            class_name=class_name,
            subclass_name=subclass_name
        )

        # Prepare JSON
        payload = json.dumps(char, default=_to_json, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)
