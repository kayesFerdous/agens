# llm/exceptions.py

class RateLimitError(Exception):
    def __init__(self, key_id: str, retry_after: int | None = None, is_daily: bool = False):
        self.key_id = key_id
        self.retry_after = retry_after
        self.is_daily = is_daily  # ← new flag

class LLMUnavailable(Exception):
    pass
