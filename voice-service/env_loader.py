"""A tiny .env loader, so the documented setup flow actually works.

The setup guide says "cp .env.example .env and add your key", but nothing in the app
ever read that file: there was no python-dotenv dependency and no loader. This is the
stdlib-only equivalent, run before the providers are configured.

Only variables that are not already present in the environment are set, so real
environment variables always win over the file.
"""

from __future__ import annotations

import os
from typing import Dict


def parse_env_file(text: str) -> Dict[str, str]:
    """Parse KEY=VALUE lines, ignoring comments, blanks and `export ` prefixes."""
    values: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Strip one pair of matching quotes; a # after whitespace starts a comment
        # only when the value is unquoted.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load_env_file(path: str) -> Dict[str, str]:
    """Load a .env file into os.environ without overriding existing variables.

    Returns the values that were applied. A missing or unreadable file is a no-op:
    the app must still start with the environment it was given.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            values = parse_env_file(handle.read())
    except OSError:
        return {}

    applied: Dict[str, str] = {}
    for key, value in values.items():
        if key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    return applied
