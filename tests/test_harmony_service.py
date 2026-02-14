"""
Tests for Harmony integration service (DATA INGESTION layer).
Validates URL format (per Harmony API / notebook), token resolution, and submit/job flow.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from services.harmony_service import (
    DEFAULT_VARIABLE,
    TEMPO_COLLECTION_IDS,
    build_tempo_rangeset_url,
    get_bearer_token,
    search_cmr_collections,
    submit_request,
    wait_for_job,
)


class TestSearchCmrCollections:
    """CMR collection search (notebook pattern: short_name / keyword)."""

    def test_short_name_returns_entries(self):
        with patch("services.harmony_service.requests.get") as mget:
            mget.return_value.json.return_value = {
                "feed": {
                    "entry": [
                        {"id": "C123-harmony_example", "title": "Example", "short_name": "harmony_example"},
                    ]
                }
            }
            mget.return_value.raise_for_status = lambda: None
            entries = search_cmr_collections(short_name="harmony_example")
        assert len(entries) == 1
        assert entries[0]["id"] == "C123-harmony_example"
        assert "short_name=harmony_example" in mget.call_args[0][0] or "harmony_example" in mget.call_args[0][0]

    def test_empty_params_returns_empty(self):
        entries = search_cmr_collections()
        assert entries == []


class TestTempoCollectionIds:
    """All five gases must have collection IDs (per DATA_INGESTION doc)."""

    def test_all_gases_defined(self):
        required = {"NO2", "CH2O", "AI", "PM", "O3"}
        assert set(TEMPO_COLLECTION_IDS.keys()) == required

    def test_collection_ids_larc_cloud(self):
        for gas, cid in TEMPO_COLLECTION_IDS.items():
            assert "LARC_CLOUD" in cid
            assert cid.startswith("C")


class TestBuildTempoRangesetUrl:
    """URL must match OGC API Coverages rangeset pattern (Harmony notebook)."""

    def test_url_contains_base_and_rangeset(self):
        start = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        url = build_tempo_rangeset_url(
            "C2930763263-LARC_CLOUD",
            DEFAULT_VARIABLE,
            -120.0, 35.0, -118.0, 37.0,
            start, end,
        )
        assert "ogc-api-coverages/1.0.0" in url
        assert "collections/" in url
        assert "coverage/rangeset" in url

    def test_subset_lon_lat_time_format(self):
        start = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        url = build_tempo_rangeset_url(
            "C123-LARC", "all",
            -120.0, 35.0, -118.0, 37.0,
            start, end,
            output_format="image/tiff",
        )
        assert "subset=lon(-120.0:-118.0)" in url
        assert "subset=lat(35.0:37.0)" in url
        assert 'subset=time("2024-06-15T10:00:00.000Z":"2024-06-15T11:00:00.000Z")' in url
        assert "format=image/tiff" in url

    def test_time_rfc3339_format(self):
        start = datetime(2020, 2, 16, 2, 0, 0, tzinfo=timezone.utc)
        end = datetime(2020, 2, 16, 3, 0, 0, tzinfo=timezone.utc)
        url = build_tempo_rangeset_url(
            "C123", "all", 0, 0, 1, 1, start, end
        )
        assert "2020-02-16T02:00:00.000Z" in url
        assert "2020-02-16T03:00:00.000Z" in url


class TestGetBearerToken:
    """Token: prefer BEARER_TOKEN; else refresh from EARTHDATA_USERNAME/PASSWORD."""

    def test_prefers_config_bearer(self):
        with patch("services.harmony_service.settings") as s:
            s.bearer_token = "mock-token"
            s.earthdata_username = None
            s.earthdata_password = None
            assert get_bearer_token() == "mock-token"

    def test_returns_none_when_no_credentials(self):
        with patch("services.harmony_service.settings") as s:
            s.bearer_token = None
            s.earthdata_username = None
            s.earthdata_password = None
            assert get_bearer_token() is None

    def test_refreshes_from_earthdata_api_when_no_bearer(self):
        with patch("services.harmony_service.settings") as s:
            s.bearer_token = None
            s.earthdata_username = "user"
            s.earthdata_password = "pass"
            with patch("services.harmony_service.requests.get") as get:
                get.return_value.status_code = 200
                get.return_value.json.return_value = [{"access_token": "refreshed-token"}]
                assert get_bearer_token() == "refreshed-token"
            with patch("services.harmony_service.requests.get") as get:
                get.return_value.status_code = 200
                get.return_value.json.return_value = []
                with patch("services.harmony_service.requests.post") as post:
                    post.return_value.raise_for_status = lambda: None
                    post.return_value.json.return_value = {"access_token": "new-token"}
                    assert get_bearer_token() == "new-token"


class TestSubmitRequest:
    """Submit GET: handle redirect (async), 200 JSON with jobID, 200 binary."""

    def test_redirect_returns_job_url_and_async(self):
        with patch("services.harmony_service._request_with_retry") as req:
            from requests import Response
            r = Response()
            r.status_code = 302
            r.headers = {"Location": "https://harmony.earthdata.nasa.gov/jobs/abc123"}
            req.return_value = r
            resp, job_url, is_async = submit_request("http://example.com", "token")
            assert resp is None
            assert "jobs/abc123" in (job_url or "")
            assert is_async is True

    def test_200_json_with_job_id_returns_async(self):
        with patch("services.harmony_service._request_with_retry") as req:
            from requests import Response
            r = Response()
            r.status_code = 200
            r.headers = {"Content-Type": "application/json"}
            r.json = lambda: {"jobID": "xyz789"}
            req.return_value = r
            resp, job_url, is_async = submit_request("http://example.com", "token")
            assert is_async is True
            assert "xyz789" in (job_url or "")

    def test_200_binary_returns_sync(self):
        with patch("services.harmony_service._request_with_retry") as req:
            from unittest.mock import MagicMock
            r = MagicMock()
            r.status_code = 200
            r.headers = {"Content-Type": "image/tiff"}
            r.content = b"\x00\x00"
            req.return_value = r
            resp, job_url, is_async = submit_request("http://example.com", "token")
            assert resp is not None
            assert job_url is None
            assert is_async is False


class TestWaitForJob:
    """Poll until status successful/complete or failed/canceled."""

    def test_successful_returns_data(self):
        with patch("services.harmony_service._request_with_retry") as req:
            from requests import Response
            r = Response()
            r.status_code = 200
            r.raise_for_status = lambda: None
            r.json = lambda: {"status": "successful", "progress": 100, "links": []}
            req.return_value = r
            data = wait_for_job("http://example.com/jobs/1", "token", poll_interval=0, max_wait_seconds=2)
            assert data.get("status") == "successful"

    def test_failed_raises(self):
        with patch("services.harmony_service._request_with_retry") as req:
            from requests import Response
            r = Response()
            r.status_code = 200
            r.raise_for_status = lambda: None
            r.json = lambda: {"status": "failed", "message": "Job failed"}
            req.return_value = r
            with pytest.raises(RuntimeError, match="failed"):
                wait_for_job("http://example.com/jobs/1", "token", poll_interval=0, max_wait_seconds=2)
