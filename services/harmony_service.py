"""
NASA Harmony (OGC API - Coverages) integration for TEMPO data.
Production endpoints: harmony.earthdata.nasa.gov, urs.earthdata.nasa.gov.
Uses BEARER_TOKEN or EARTHDATA_USERNAME/EARTHDATA_PASSWORD from config.
"""
import logging
import time
from base64 import b64encode
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urljoin

import requests

from urllib.parse import urlencode

from config import (
    CMR_BASE_URL,
    HARMONY_BASE_URL,
    URSA_TOKEN_URL,
    URSA_TOKENS_URL,
    settings,
)

logger = logging.getLogger(__name__)

# TEMPO collection IDs (from CMR; do not call CMR on every run)
TEMPO_COLLECTION_IDS = {
    "NO2": "C2930763263-LARC_CLOUD",
    "CH2O": "C2930763264-LARC_CLOUD",
    "AI": "C2930763265-LARC_CLOUD",
    "PM": "C2930763266-LARC_CLOUD",
    "O3": "C2930763267-LARC_CLOUD",
}

# Default variable for coverage request (Harmony "collections" = variables; "all" often works)
DEFAULT_VARIABLE = "all"


def search_cmr_collections(
    short_name: Optional[str] = None,
    version: Optional[int] = None,
    keyword: Optional[str] = None,
) -> list[dict]:
    """
    Search CMR for collections (notebook pattern: short_name + version; optional keyword).
    CMR does not require auth for collection search.
    Returns list of feed entry dicts (id, title, short_name, summary, etc.).
    """
    params: dict = {}
    if short_name:
        params["short_name"] = short_name
    if version is not None:
        params["version"] = version
    if keyword:
        params["keyword"] = keyword
    if not params:
        return []
    url = f"{CMR_BASE_URL.rstrip('/')}/search/collections.json?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        entries = data.get("feed", {}).get("entry", [])
        return list(entries)
    except Exception as e:
        logger.exception("CMR collection search failed: %s", e)
        return []


def search_cmr_granules(
    collection_id: str,
    start_time: datetime,
    end_time: datetime,
    west: float,
    south: float,
    east: float,
    north: float,
    page_size: int = 5,
) -> list[dict]:
    """
    Search CMR for granules in a collection within temporal and bbox.
    No auth required. Returns list of granule entry dicts (id, title, time_start, etc.).
    Use to find when/where data exists before calling Harmony.
    """
    temporal = f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')},{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    bbox = f"{west},{south},{east},{north}"
    # CMR granule search: concept_id (or collection_concept_id) for collection
    params = {
        "concept_id": collection_id,
        "temporal": temporal,
        "bounding_box": bbox,
        "page_size": page_size,
    }
    url = f"{CMR_BASE_URL.rstrip('/')}/search/granules.json?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        entries = data.get("feed", {}).get("entry", [])
        return list(entries)
    except Exception as e:
        logger.debug("CMR granule search failed (non-fatal): %s", e)
        return []


def get_bearer_token() -> Optional[str]:
    """
    Prefer BEARER_TOKEN from config. If missing, obtain token via Earthdata API
    using EARTHDATA_USERNAME and EARTHDATA_PASSWORD.
    """
    if settings.bearer_token:
        return settings.bearer_token
    if not settings.earthdata_username or not settings.earthdata_password:
        logger.warning("No bearer token and no Earthdata credentials; Harmony requests will fail.")
        return None
    basic = b64encode(
        f"{settings.earthdata_username}:{settings.earthdata_password}".encode("ascii")
    ).decode("ascii")
    headers = {"Authorization": f"Basic {basic}"}
    try:
        # Try existing tokens first (GET)
        r = requests.get(URSA_TOKENS_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("access_token")
        # Create new token (POST)
        r = requests.post(URSA_TOKEN_URL, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        logger.exception("Failed to get Earthdata bearer token: %s", e)
        return None


def build_tempo_rangeset_url(
    collection_id: str,
    variable: str,
    west: float,
    south: float,
    east: float,
    north: float,
    start_time: datetime,
    end_time: datetime,
    output_format: str = "image/tiff",
) -> str:
    """
    Build Harmony OGC API Coverages rangeset URL for subset by lon, lat, time.
    """
    st = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    et = end_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    base = (
        f"{HARMONY_BASE_URL}/{collection_id}/ogc-api-coverages/1.0.0"
        f"/collections/{variable}/coverage/rangeset"
    )
    params = (
        f"subset=lon({west}:{east})"
        f"&subset=lat({south}:{north})"
        f"&subset=time(\"{st}\":\"{et}\")"
        f"&format={output_format}"
    )
    return f"{base}?{params}"


def _request_with_retry(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    max_retries: int = 3,
) -> requests.Response:
    """GET or POST with exponential backoff on 429/500."""
    session = requests.Session()
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                r = session.get(url, headers=headers, timeout=60, allow_redirects=False)
            else:
                r = session.post(url, headers=headers, timeout=60, allow_redirects=False)
        except requests.RequestException as e:
            logger.warning("Request attempt %s failed: %s", attempt + 1, e)
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503):
            if attempt == max_retries - 1:
                r.raise_for_status()
            delay = 10 * (2 ** attempt)
            logger.warning("HTTP %s, retry in %s s", r.status_code, delay)
            time.sleep(delay)
            continue
        return r
    return r


def submit_request(url: str, token: Optional[str]) -> Tuple[Optional[requests.Response], Optional[str], bool]:
    """
    Submit Harmony request (GET). Returns (response, job_url_or_none, is_async).
    - If 302/303/307: job_url is the Location, is_async=True, response is None.
    - If 200 JSON with jobID: job_url is jobs/{id}, is_async=True; response is the response.
    - If 200 binary (GeoTIFF): response has .content, job_url None, is_async=False.
    - If 200 JSON with data links: response has .json(), job_url is first data href, is_async=False.
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = _request_with_retry("GET", url, headers=headers)
    if r.status_code in (302, 303, 307):
        location = r.headers.get("Location")
        if location:
            if not location.startswith("http"):
                location = urljoin(HARMONY_BASE_URL + "/", location)
            logger.info("Harmony async job: %s", location)
            return (None, location, True)
    if r.status_code == 200:
        ct = r.headers.get("Content-Type", "")
        if "application/json" in ct:
            data = r.json()
            job_id = data.get("jobID")
            if job_id:
                job_url = urljoin(HARMONY_BASE_URL + "/", f"jobs/{job_id}")
                return (r, job_url, True)
            links = data.get("links", [])
            for link in links:
                if link.get("rel") == "data" and link.get("href"):
                    return (r, link["href"], False)
            return (r, None, False)
        # Binary response (sync GeoTIFF)
        return (r, None, False)
    if r.status_code in (400, 403):
        try:
            body = r.text[:500] if r.text else "(empty)"
            logger.warning("Harmony %s. Response: %s", r.status_code, body)
        except Exception:
            pass
    r.raise_for_status()
    return (None, None, False)


def wait_for_job(
    job_url: str,
    token: Optional[str],
    poll_interval: int = 10,
    max_wait_seconds: int = 3600,
) -> dict:
    """
    Poll Harmony job URL until status is successful/complete or failed/canceled.
    Returns the final JSON response.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    start = time.time()
    while True:
        if time.time() - start > max_wait_seconds:
            raise TimeoutError(f"Harmony job did not complete within {max_wait_seconds}s")
        r = _request_with_retry("GET", job_url, headers=headers)
        r.raise_for_status()
        data = r.json()
        status = (data.get("status") or "").lower()
        progress = data.get("progress", 0)
        logger.info("Harmony job status=%s progress=%s", status, progress)
        if status in ("successful", "complete"):
            return data
        if status in ("failed", "canceled", "error"):
            raise RuntimeError(f"Harmony job {status}: {data.get('message', data)}")
        time.sleep(poll_interval)


def download_to_temp_file(url: str, token: Optional[str], suffix: str = ".tif") -> str:
    """Download URL to a temp file and return its path."""
    import tempfile

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(url, headers=headers, timeout=120, stream=True)
    r.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with open(fd, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception:
        import os

        try:
            os.unlink(path)
        except Exception:
            pass
        raise
    return path


def fetch_tempo_geotiff(
    gas: str,
    west: float,
    south: float,
    east: float,
    north: float,
    start_time: datetime,
    end_time: datetime,
) -> Optional[str]:
    """
    Build Harmony request for the given gas and bbox/time, submit, wait for job
    if async, download GeoTIFF to a temp file. Returns path to temp file (caller
    must unlink when done) or None on failure.
    """
    import tempfile
    import os

    collection_id = TEMPO_COLLECTION_IDS.get(gas)
    if not collection_id:
        logger.error("Unknown gas: %s", gas)
        return None
    token = get_bearer_token()
    if not token:
        logger.error("No Harmony bearer token available")
        return None
    url = build_tempo_rangeset_url(
        collection_id, DEFAULT_VARIABLE, west, south, east, north, start_time, end_time
    )
    logger.info("Submitting Harmony request for %s", gas)
    try:
        resp, job_url, is_async = submit_request(url, token)
        if is_async and job_url:
            data = wait_for_job(job_url, token)
            links = [l for l in data.get("links", []) if l.get("rel") == "data"]
            if not links:
                logger.error("No data links in job response")
                return None
            download_url = links[0].get("href")
            if not download_url:
                return None
            path = download_to_temp_file(download_url, token, suffix=".tif")
            logger.info("Downloaded GeoTIFF to %s", path)
            return path
        if not is_async and resp is not None:
            ct = resp.headers.get("Content-Type", "")
            if "image/tiff" in ct or "octet-stream" in ct:
                fd, path = tempfile.mkstemp(suffix=".tif")
                try:
                    os.write(fd, resp.content)
                finally:
                    os.close(fd)
                return path
            if job_url:
                path = download_to_temp_file(job_url, token, suffix=".tif")
                return path
        return None
    except Exception as e:
        logger.exception("Harmony fetch failed for %s: %s", gas, e)
        return None
