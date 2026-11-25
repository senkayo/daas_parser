import random
import time

from curl_cffi import requests

from core.logger import setup_logger

logger = setup_logger(__name__)


def fetch_html(
    url: str,
    timeout: int = 10,
    delay_range: tuple[float, float] = (1.0, 3.0),
    impersonate: str = "chrome",
) -> str | None:
    """Fetch HTML content from a URL using curl_cffi with optional randomized delay."""
    if delay_range is not None:
        min_delay, max_delay = delay_range
        if min_delay < 0 or max_delay < 0 or min_delay > max_delay:
            raise ValueError(
                f"Invalid delay_range {delay_range}: expected 0 <= min_delay <= max_delay."
            )
        if max_delay > 0:
            time.sleep(random.uniform(min_delay, max_delay))

    try:
        response = requests.get(url, impersonate=impersonate, timeout=timeout)
        if response.status_code == 200:
            logger.info("Success: %s", url)
            return response.text

        logger.warning("Ошибка сервера %s для %s", response.status_code, url)
        return None
    except requests.errors.RequestsError as exc:
        logger.error("Сетевая ошибка или таймаут для %s: %s", url, exc)
        return None
