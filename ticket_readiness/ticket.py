"""Ticket parsing: tiny front matter + markdown sections.

Deliberately dependency-free. Front matter supports `key: value` and
`key: [a, b]` lists; sections are `## Heading` blocks. Anything else is body.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class TicketError(ValueError):
    """Raised for unreadable or structurally broken ticket files."""


@dataclass
class Ticket:
    id: str
    title: str
    body: str
    meta: dict[str, object] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)
    source: str = "<memory>"

    def section(self, *names: str) -> str | None:
        """Case-insensitive lookup; the first matching name wins."""
        lowered = {k.lower(): v for k, v in self.sections.items()}
        for name in names:
            if name.lower() in lowered:
                return lowered[name.lower()]
        return None

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}"

    @property
    def is_empty(self) -> bool:
        return not self.body.strip()


def _parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] if inner else []
    return raw


def parse_ticket(text: str, source: str = "<memory>") -> Ticket:
    if not text.strip():
        raise TicketError(f"{source}: file is empty")
    meta: dict[str, object] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise TicketError(f"{source}: unterminated front matter")
        for line in parts[1].strip().splitlines():
            if ":" not in line:
                raise TicketError(f"{source}: bad front matter line {line!r}")
            key, _, value = line.partition(":")
            meta[key.strip()] = _parse_value(value)
        body = parts[2]
    ticket_id = str(meta.get("id") or Path(source).stem)
    title = str(meta.get("title") or "").strip()
    if not title:
        raise TicketError(f"{source}: ticket has no title")
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[m.group(1)] = body[m.end():end].strip()
    return Ticket(id=ticket_id, title=title, body=body.strip(), meta=meta, sections=sections, source=source)


def load_ticket(path: str | Path) -> Ticket:
    path = Path(path)
    if not path.exists():
        raise TicketError(f"{path}: not found")
    try:
        return parse_ticket(path.read_text(encoding="utf-8"), source=str(path))
    except UnicodeDecodeError as exc:
        raise TicketError(f"{path}: not UTF-8 text") from exc
