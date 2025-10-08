"""
API handler for the Daggerheart character generator.

This module exposes a single HTTP endpoint which returns a complete
Daggerheart character in JSON form.  It relies on the core
``daggerheart_character_creator`` module to construct characters and
applies optional equipment selections via the ``apply_equipment``
function.  The handler accepts the following query parameters:

* ``level`` – integer from 1 to 10 (default 1)
* ``archetype`` – one of Tank, Damage, Sneaky, Support, Healer,
  Face, Control (required)
* ``class`` – optional class name to lock in (e.g. "Druid")
* ``subclass`` – optional subclass name to lock in (e.g. "Wayfinder")
* ``primary`` – optional primary weapon name from the Tier 1 table
* ``secondary`` – optional secondary weapon name from the Tier 1 table
* ``armor`` – optional armour name from the Tier 1 table

For example::

    /api/generate?level=3&archetype=Tank&class=Guardian&primary=Longsword&armor=Leather%20Armor

The response is a JSON object representing the character.  Nested
dataclasses are flattened into dictionaries.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

# Ensure we can import the character creator from the repository root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from daggerheart_character_creator import create_character, apply_equipment


def _to_json(obj):
    """Convert dataclass instances and other objects to JSON serialisable forms."""
    if hasattr(obj, '__dict__'):
        return {k: _to_json(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_json(x) for x in obj]
    return obj


class handler(BaseHTTPRequestHandler):  # type: ignore
    """Simple HTTP handler for generating characters."""

    def do_GET(self) -> None:
        # Parse the query string
        qs = parse_qs(urlparse(self.path).query)
        level = int(qs.get('level', ['1'])[0])
        archetype = qs.get('archetype', [''])[0]
        class_name = qs.get('class', [None])[0]
        subclass_name = qs.get('subclass', [None])[0]
        primary = qs.get('primary', [None])[0]
        secondary = qs.get('secondary', [None])[0]
        armour = qs.get('armor', [None])[0]
        # Validate required fields
        if not archetype:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'archetype parameter is required'}).encode('utf-8'))
            return
        try:
            # Create the base character
            char = create_character(level, archetype, class_name=class_name, subclass_name=subclass_name)
            # Apply equipment if provided
            apply_equipment(char, primary=primary, secondary=secondary, armour=armour)
            # Convert to JSON
            data = _to_json(char)
            payload = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(exc)}).encode('utf-8'))