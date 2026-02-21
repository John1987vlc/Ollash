from colorama import Fore, Style


class TokenTracker:
    """Track token usage across the session"""

    def __init__(self):
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_total_tokens = 0
        self.request_count = 0
        self.last_request_tokens = 0

    def add_usage(self, prompt_tokens: int, completion_tokens: int):
        """Add token usage from a request"""
        self.session_prompt_tokens += prompt_tokens
        self.session_completion_tokens += completion_tokens
        total = prompt_tokens + completion_tokens
        self.session_total_tokens += total
        self.last_request_tokens = total
        self.request_count += 1

    def get_session_summary(self) -> str:
        """Get formatted session summary"""
        avg = self.session_total_tokens // max(1, self.request_count)
        return f"""
{Fore.CYAN}{"=" * 60}
📊 Token Usage Summary:
{"=" * 60}{Style.RESET_ALL}
  • Requests: {self.request_count}
  • Prompt tokens: {self.session_prompt_tokens:,}
  • Completion tokens: {self.session_completion_tokens:,}
  • Total tokens: {self.session_total_tokens:,}
  • Avg per request: {avg:,}
{Fore.CYAN}{"=" * 60}{Style.RESET_ALL}"""

    def display_current(self):
        """Display current usage"""
        print(
            f"{Fore.MAGENTA}💭 Tokens: {self.last_request_tokens:,} | "
            f"Session: {self.session_total_tokens:,}{Style.RESET_ALL}"
        )
