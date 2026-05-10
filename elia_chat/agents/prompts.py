from __future__ import annotations


def build_group_prompt(
    *,
    agent_name: str,
    peer_name: str,
    user_prompt: str,
    transcript: str,
) -> str:
    transcript = transcript.strip() or "(No prior room messages.)"
    return f"""You are {agent_name} inside a terminal group chat managed by Cafedelia.

The other agent in the room is {peer_name}. The human user may ask one or both of you to reason, review, code, or compare approaches.

Operate as {agent_name}. Be concise but technically complete. If you use tools, summarize what you did and why. Do not impersonate {peer_name}; respond only as yourself.

Recent room transcript:
{transcript}

Latest user message:
{user_prompt}
"""
