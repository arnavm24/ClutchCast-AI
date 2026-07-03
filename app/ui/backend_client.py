import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from ui.config import BACKEND_BASE_URL


def fetch_backend_json(path: str, timeout: float = 6.0) -> dict:
    url = f"{BACKEND_BASE_URL}{path}"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"ok": 200 <= response.status < 300, "status_code": response.status, "data": payload, "url": url}
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except Exception:
            payload = {"error": str(error)}
        return {"ok": False, "status_code": error.code, "data": payload, "url": url}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status_code": None, "data": {"error": str(error)}, "url": url}
