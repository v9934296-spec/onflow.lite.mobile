"""Shared Gemini pipeline errors (job failure_reason values)."""


class GeminiPipelineError(Exception):
    """Maps to terminal job failure_reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)
