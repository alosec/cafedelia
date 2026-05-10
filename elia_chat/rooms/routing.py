from __future__ import annotations


def parse_recipients(
    text: str, default: tuple[str, ...] = ("claude", "codex")
) -> tuple[str, ...]:
    lowered = text.lower()
    mentions_claude = "@claude" in lowered or "claude:" in lowered
    mentions_codex = "@codex" in lowered or "codex:" in lowered

    if mentions_claude and mentions_codex:
        return ("claude", "codex")
    if mentions_claude:
        return ("claude",)
    if mentions_codex:
        return ("codex",)
    return default
