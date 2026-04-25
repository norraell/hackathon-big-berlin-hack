"""LLM layer.

Streaming Gemini client (``client.py``), system prompt and language-specific
preambles (``prompts.py``), and the JSON schemas for tool/function calls
(``tools.py``). Gemini handles both STT and dialog/tool-calling — same
vendor, one auth path. Tool calls are the only path from the LLM to the
database (CLAUDE.md §5.2).
"""
