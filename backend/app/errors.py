class InvalidPRUrlError(Exception):
    """Raised when the provided URL is not a valid GitHub PR URL."""


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OpenAIAPIError(Exception):
    """Raised when the OpenAI API returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
