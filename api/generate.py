"""
API handler for the Daggerheart character generator.

This module exposes a single HTTP endpoint which returns a complete
Daggerheart character in JSON form.  It relies on the core
``daggerheart_character_creator`` module to construct characters and
applies optional equipment selections via the ``apply_equipment``
function.  The handler accepts the following query parameters:

* ``level`` – integer from 1 to 10 (default 1)
* ``archetype`` – optional archetype string.  Choose from ``Tank``,
  ``Damage``, ``Sneaky``, ``Support``, ``Healer``, ``Face`` or ``Control``.
  If omitted, the handler will attempt to infer a sensible archetype
  based on the chosen class, or fall back to ``Damage`` if neither
  class nor archetype is provided.
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
from typing import Optional

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
    """
    Simple HTTP handler for generating characters.

    This handler returns structured JSON for a Daggerheart character and
    will include error details on failure.  All query parameters are
    optional.  If the class is omitted the generator will choose a
    random class.  If the archetype is omitted it will infer one
    from the class or default to ``Random`` for a balanced build.
    """

    def do_GET(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        try:
            # Parse level and ensure it is an integer between 1 and 10
            lvl_str = qs.get('level', ['1'])[0]
            level = int(lvl_str)
            if not (1 <= level <= 10):
                raise ValueError('level must be between 1 and 10')
        except Exception:
            level = 1
        # Helper to strip blank/placeholder values to None
        def norm(val: Optional[str]) -> Optional[str]:
            if val is None:
                return None
            v = str(val).strip()
            if not v or v.lower().startswith('none') or v.startswith('—'):
                return None
            return v
        # Extract and normalise parameters
        class_name = norm(qs.get('class', [None])[0])
        subclass_name = norm(qs.get('subclass', [None])[0])
        primary = norm(qs.get('primary', [None])[0])
        secondary = norm(qs.get('secondary', [None])[0])
        armour = norm(qs.get('armor', [None])[0])
        archetype = norm(qs.get('archetype', [None])[0])
        # Infer a sensible archetype if none provided
        if archetype is None:
            default_map = {
                'Guardian': 'Tank',
                'Warrior': 'Damage',
                'Rogue': 'Sneaky',
                'Ranger': 'Sneaky',
                'Druid': 'Support',
                'Bard': 'Face',
                'Seraph': 'Support',
                'Sorcerer': 'Damage',
                'Wizard': 'Control',
            }
            archetype = default_map.get(class_name, 'Random')
        try:
            # Build the character
            char = create_character(level, archetype, class_name=class_name, subclass_name=subclass_name)
            # Apply equipment if any
            if primary or secondary or armour:
                apply_equipment(char, primary=primary, secondary=secondary, armour=armour)
            # Hide the archetype in the returned structure
            char.archetype = None  # type: ignore
            # Serialize
            data = _to_json(char)
            body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            # On failure return error and traceback for debugging
            import traceback
            err = {
                'error': str(exc),
                'trace': traceback.format_exc(),
            }
            body = json.dumps(err, ensure_ascii=False, indent=2).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)