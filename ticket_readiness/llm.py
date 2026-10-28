"""Optional model-backed rewrite suggestion.

The rules engine produces every finding. A model is only asked to draft a
clearer version of the ticket *given those findings*; the draft is labelled as
model-generated and never changes the score or verdict.
"""
from __future__ import annotations

import os
from typing import Protocol

from .checks import Finding
from .ticket import Ticket


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    name: str

    def rewrite(self, ticket: Ticket, findings: list[Finding]) -> str | None: ...


class RulesOnlyProvider:
    name = "rules"

    def rewrite(self, ticket: Ticket, findings: list[Finding]) -> str | None:  # noqa: ARG002
        return None


SYSTEM = (
    "You draft clearer engineering tickets. Rewrite the ticket to address the listed findings. "
    "Keep every fact from the original; do not invent requirements, numbers, or systems. "
    "Where a decision is needed, write 'OPEN QUESTION:' instead of deciding. "
    "Use sections: Summary, Acceptance criteria (Given/When/Then), Out of scope, Dependencies, Open questions."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None, client=None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("TICKET_READINESS_MODEL")
        if client is not None:
            self._client = client
            return
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        if not self.model:
            raise ProviderError("TICKET_READINESS_MODEL is not set")
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("install the optional extra: pip install -e '.[llm]'") from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def rewrite(self, ticket: Ticket, findings: list[Finding]) -> str | None:
        bullet = "\n".join(f"- ({f.kind}, {f.severity}) {f.message} {f.suggestion}".strip() for f in findings)
        content = f"TICKET {ticket.id}: {ticket.title}\n\n{ticket.body}\n\nFINDINGS:\n{bullet}"
        try:
            resp = self._client.messages.create(model=self.model, max_tokens=800, system=SYSTEM,
                                                messages=[{"role": "user", "content": content}])
        except Exception as exc:
            raise ProviderError(f"model call failed: {exc}") from exc
        text = "".join(getattr(b, "text", "") for b in resp.content).strip()
        return text or None


def provider_from_env() -> Provider:
    kind = os.environ.get("TICKET_READINESS_PROVIDER", "rules").lower()
    if kind == "rules":
        return RulesOnlyProvider()
    if kind == "anthropic":
        return AnthropicProvider()
    raise ProviderError(f"unknown provider {kind!r} (use 'rules' or 'anthropic')")
