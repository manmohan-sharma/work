"""
Code Review Exercise 4: Simple API Client

Reviewed against the "Key Issues to Find" section of README.md and fixed
(original kept alongside as api_client.py.orig):

1. Network error handling -> connection/timeout errors are caught and retried,
   then reported instead of escaping as a bare Exception.
2. HTTP status code handling -> 400/401/403/404/429 and 5xx each get their own
   explanation instead of a generic failure.
3. Error information -> every method returns a structured dict describing what
   went wrong (including the status code) instead of None or a bare boolean.
4. Input validation -> base_url, api_key, user_id and data are validated up
   front with clear ValueError messages.

Rating (of the original): Fair -- the retry/backoff logic was sound, but
callers had no reliable way to tell success from failure.
Recommendation: Modify (applied below).
"""

import time

import requests


class APIClient:
    def __init__(self, base_url, api_key, timeout=10, max_retries=3, base_delay=1):
        # Validate configuration before anything else can use it
        if not base_url or not str(base_url).strip():
            raise ValueError("Base URL cannot be empty")
        if not api_key or not str(api_key).strip():
            raise ValueError("API key cannot be empty")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than 0 seconds")
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        if base_delay < 0:
            raise ValueError("base_delay cannot be negative")

        self.base_url = str(base_url).strip().rstrip("/")  # Remove trailing slash
        self.api_key = api_key
        self.timeout = timeout  # Reasonable timeout in seconds
        self.max_retries = max_retries  # Maximum retry attempts
        self.base_delay = base_delay  # Base delay for exponential backoff in seconds

    @staticmethod
    def _validate_user_id(user_id):
        """Reject empty/whitespace user IDs. Returns the ID as a clean string."""
        if user_id is None:
            raise ValueError("User ID cannot be empty")
        cleaned = str(user_id).strip()
        if not cleaned:
            raise ValueError("User ID cannot be empty")
        return cleaned

    def _calculate_backoff_delay(self, attempt):
        """Calculate exponential backoff delay: base_delay * 2^attempt"""
        return self.base_delay * (2 ** attempt)

    def _should_retry(self, exception=None, status_code=None):
        """Determine if request should be retried based on error type"""
        # Retry on network errors (ConnectionError, Timeout)
        if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
            return True

        # Retry on 5xx server errors
        if status_code is not None and 500 <= status_code < 600:
            return True

        # Don't retry on 4xx client errors
        return False

    def _network_error(self, exception, url):
        """Turn a network exception into a user-facing error dict."""
        if isinstance(exception, requests.Timeout):
            message = (
                f"Request timed out: the server did not respond within "
                f"{self.timeout} seconds"
            )
        else:
            message = (
                f"Failed to connect to the server at {url}. "
                f"Please check your network connection."
            )
        return {"error": message, "status_code": None}

    @staticmethod
    def _describe_status(status_code):
        """Human-readable explanation for a non-200 status code."""
        known = {
            400: "Bad request - check the data that was sent",
            401: "Unauthorized - check API key",
            403: "Forbidden - this API key does not have access",
            404: "User not found",
            429: "Rate limited - wait before trying again",
        }
        if status_code in known:
            return known[status_code]
        if status_code >= 500:
            return "Server error - try again later"
        return f"Request failed with status {status_code}"

    def _send(self, request_fn, url, **kwargs):
        """Send a request, retrying network and 5xx errors with backoff.

        Returns (response, error). Exactly one of the two is None, so callers
        never have to guess whether the call succeeded.
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = request_fn(url, timeout=self.timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = self._network_error(e, url)
            except requests.RequestException as e:
                # Not retryable (malformed URL, too many redirects, ...)
                return None, {"error": f"Request failed: {e}", "status_code": None}
            else:
                if not self._should_retry(status_code=response.status_code):
                    return response, None
                last_error = {
                    "error": self._describe_status(response.status_code),
                    "status_code": response.status_code,
                }

            if attempt < self.max_retries - 1:
                time.sleep(self._calculate_backoff_delay(attempt))

        return None, last_error

    def get_user_data(self, user_id):
        """Fetch a user. Returns the user dict, or {"error": ..., "status_code": ...}."""
        user_id = self._validate_user_id(user_id)

        url = f"{self.base_url}/users/{user_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response, error = self._send(requests.get, url, headers=headers)
        if error:
            return error

        if response.status_code != 200:
            return {
                "error": self._describe_status(response.status_code),
                "status_code": response.status_code,
            }

        try:
            return response.json()
        except ValueError:
            # Covers json.JSONDecodeError and requests' own JSONDecodeError
            return {
                "error": "Invalid response: the server returned malformed JSON",
                "status_code": response.status_code,
            }

    def update_user(self, user_id, data):
        """Update a user. Returns {"success": bool, ...} describing the outcome."""
        user_id = self._validate_user_id(user_id)
        if not isinstance(data, dict) or not data:
            raise ValueError("Data must be a non-empty dictionary")

        url = f"{self.base_url}/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response, error = self._send(requests.put, url, headers=headers, json=data)
        if error:
            return {"success": False, **error}

        if response.status_code == 200:
            return {
                "success": True,
                "message": "User updated successfully",
                "status_code": 200,
            }

        return {
            "success": False,
            "error": self._describe_status(response.status_code),
            "status_code": response.status_code,
        }
