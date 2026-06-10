import logging
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("outreach_pipeline")

class APIException(Exception):
    """Base exception class for API errors."""
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

class RateLimitException(APIException):
    """Exception raised when hitting 429 rate limit."""
    pass

class BaseClient:
    """Base client for API integrations containing retry and rate limiting logic."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()

    def _should_retry(self, exception):
        """Returns True if the exception is transient and should be retried."""
        if isinstance(exception, requests.exceptions.HTTPError):
            status = exception.response.status_code
            return status >= 500 or status == 429
        return isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout, RateLimitException)),
        reraise=True
    )
    def _send_request(self, method: str, path: str, headers: dict = None, params: dict = None, json_data: dict = None) -> dict:
        """Sends HTTP request with built-in retries, rate limiting handlers, and error catching."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        
        # Merge headers
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        try:
            logger.debug(f"API Request: {method} {url} | Params: {params} | Body: {json_data}")
            response = self.session.request(
                method=method,
                url=url,
                headers=req_headers,
                params=params,
                json=json_data,
                timeout=15
            )

            # Check for rate limits (429)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else 5
                rate_limit_headers = {k: v for k, v in response.headers.items() if 'rate' in k.lower() or 'left' in k.lower() or 'reset' in k.lower()}
                logger.warning(f"Rate limit hit (429) on {url}. Rate limit headers: {rate_limit_headers}. Retrying after {wait_time}s...")
                time.sleep(wait_time)
                raise RateLimitException(f"Rate limit exceeded on {url}", status_code=429, response_text=response.text)

            # Raise on other HTTP errors
            response.raise_for_status()
            
            # Try to return JSON, fallback to raw text if not JSON
            try:
                return response.json()
            except ValueError:
                return {"text": response.text}

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            response_text = http_err.response.text
            msg = f"HTTP Error {status_code} calling {url}: {response_text}"
            logger.error(msg)
            raise APIException(msg, status_code=status_code, response_text=response_text)
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as conn_err:
            msg = f"Connection error calling {url}: {str(conn_err)}"
            logger.error(msg)
            raise conn_err
            
        except Exception as e:
            if not isinstance(e, RateLimitException):
                msg = f"Unexpected error calling {url}: {str(e)}"
                logger.error(msg)
                raise APIException(msg)
            raise e
