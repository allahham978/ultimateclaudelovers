"""
Tests for the knowledge-base updater integration — kb_updater.py, cache
invalidation in knowledge_base.py, /kb/* endpoints in main.py, and the
background scheduler.

Covers:
  - KBUpdater.run_update() with mocked EUR-Lex + Claude API
  - JSON patch application and Pydantic validation gate
  - Atomic file writes and backup rotation
  - reload_requirements() cache invalidation
  - POST /kb/update and GET /kb/status endpoints
  - Background scheduler lifespan logic
  - Safety: failed validation does NOT overwrite master_requirements.json
  - Existing knowledge_base.py functions still work (regression)
"""

import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest

from tools.kb_updater import (
    KBUpdater,
    _apply_json_patch,
    _safe_parse_json,
    _validate_csrd_documents,
    _extract_kb_schema,
    get_tracked_celex_ids,
    read_meta,
    _write_meta,
    _KB_PATH,
    _META_PATH,
    _BACKUP_DIR,
    _AUDIT_DIR,
    _MAX_BACKUPS,
)
from tools.knowledge_base import load_requirements, reload_requirements
from data.schema import CSRDReportingRequirements


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Must be > 5000 chars for the EUR-Lex fetch to accept it
SAMPLE_DIRECTIVE_HTML = (
    "<html><body>"
    "THE EUROPEAN PARLIAMENT AND THE COUNCIL OF THE EUROPEAN UNION, "
    "Having regard to the Treaty on the Functioning of the European Union, "
    "and in particular Article 50(1) thereof, Having regard to the proposal "
    "from the European Commission, After transmission of the draft legislative "
    "act to the national parliaments, Having regard to the opinion of the "
    "European Economic and Social Committee, Acting in accordance with the "
    "ordinary legislative procedure, Whereas: "
    + " ".join(
        f"({i}) This is recital number {i} providing additional context and "
        f"justification for the regulatory changes proposed in this directive. "
        f"The European Union seeks to ensure sustainability reporting standards "
        f"are applied consistently across all Member States. "
        for i in range(1, 40)
    )
    + " Article 1 Subject matter. "
    "This Directive amends Directive 2013/34/EU as regards sustainability reporting. "
    "Article 2 Amendments. "
    "The employee threshold is changed from 500 to 250. "
    "Article 3 Transposition. "
    "Member States shall transpose this Directive by 1 January 2026. "
    "</body></html>"
)

MOCK_ANALYSIS_RESPONSE = json.dumps({
    "directive_title": "Test Directive 2025/1234",
    "celex_id": "32025L1234",
    "publication_date": "2025-01-15",
    "effective_date": "2025-07-01",
    "implementation_deadline": "2026-01-01",
    "amends_directives": ["32022L2464"],
    "summary": "A test directive for unit testing purposes.",
    "affected_entity_types": ["large companies"],
    "key_changes": [
        {
            "article": "Article 2",
            "topic": "Employee threshold",
            "change_description": "Threshold reduced",
            "previous_rule": "500 employees",
            "new_rule": "250 employees",
        }
    ],
    "new_obligations": [],
    "removed_obligations": [],
    "amended_thresholds": [{"metric": "employees", "old_value": "500", "new_value": "250"}],
    "implementation_deadlines": [],
    "reporting_changes": [],
    "scope_changes": [],
})

MOCK_AFFECTED_SECTIONS = json.dumps(["csrd_reporting_requirements"])

# A patch that does a harmless no-op replace on a known-valid field
MOCK_PATCH_OPS = json.dumps([
    {
        "op": "replace",
        "path": "/csrd_reporting_requirements/0/mandatory_note",
        "value": "Updated by test directive 2025/1234",
    }
])


@pytest.fixture
def kb_snapshot():
    """Save and restore master_requirements.json around the test."""
    original = _KB_PATH.read_bytes()
    yield original
    _KB_PATH.write_bytes(original)
    # Clear cache so other tests aren't affected
    load_requirements.cache_clear()


@pytest.fixture
def clean_meta():
    """Remove kb_update_meta.json before and after test."""
    if _META_PATH.exists():
        _META_PATH.unlink()
    yield
    if _META_PATH.exists():
        _META_PATH.unlink()


@pytest.fixture
def clean_backups():
    """Remove backup dir before and after test."""
    if _BACKUP_DIR.exists():
        shutil.rmtree(_BACKUP_DIR)
    yield
    if _BACKUP_DIR.exists():
        shutil.rmtree(_BACKUP_DIR)


@pytest.fixture
def clean_audit():
    """Remove audit trail dir before and after test."""
    if _AUDIT_DIR.exists():
        shutil.rmtree(_AUDIT_DIR)
    yield
    if _AUDIT_DIR.exists():
        shutil.rmtree(_AUDIT_DIR)


def _make_mock_stream(response_text: str):
    """Create a mock for anthropic client.messages.stream() context manager."""
    mock_stream_ctx = MagicMock()
    mock_stream = MagicMock()
    mock_stream.text_stream = iter([response_text])
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    return mock_stream_ctx


def _make_mock_anthropic_client(responses: list[str]):
    """Create a mock Anthropic client that returns responses sequentially."""
    mock_client = MagicMock()
    side_effects = [_make_mock_stream(r) for r in responses]
    mock_client.messages.stream.side_effect = side_effects
    return mock_client


def _mock_httpx_get(url, **kwargs):
    """Mock httpx.get to return fake directive HTML."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_DIRECTIVE_HTML
    return mock_response


# ===========================================================================
# Unit tests: JSON utilities
# ===========================================================================


class TestSafeParseJson:
    """Tests for _safe_parse_json() utility."""

    def test_plain_json(self):
        assert _safe_parse_json('{"a": 1}') == {"a": 1}

    def test_json_array(self):
        assert _safe_parse_json('[1, 2, 3]') == [1, 2, 3]

    def test_markdown_fenced(self):
        assert _safe_parse_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_with_prose(self):
        raw = 'Here is the result:\n{"a": 1}\nEnd.'
        assert _safe_parse_json(raw) == {"a": 1}

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _safe_parse_json("not json at all")


class TestExtractKbSchema:
    """Tests for _extract_kb_schema()."""

    def test_basic_structure(self):
        kb = {"key": "value", "nested": {"inner": [1, 2]}}
        schema = _extract_kb_schema(kb)
        assert schema["key"] == "str"
        assert isinstance(schema["nested"], dict)

    def test_depth_limit(self):
        deep = {"a": {"b": {"c": {"d": "val"}}}}
        schema = _extract_kb_schema(deep, depth_limit=2)
        assert schema["a"]["b"] == "..."


# ===========================================================================
# Unit tests: JSON Patch application
# ===========================================================================


class TestApplyJsonPatch:
    """Tests for _apply_json_patch() — RFC 6902 operations."""

    def test_replace_field(self):
        doc = {"name": "old"}
        ops = [{"op": "replace", "path": "/name", "value": "new"}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert result["name"] == "new"
        assert len(applied) == 1
        assert applied[0]["old_value"] == "old"
        assert len(skipped) == 0

    def test_add_field(self):
        doc = {"a": 1}
        ops = [{"op": "add", "path": "/b", "value": 2}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert result["b"] == 2
        assert len(applied) == 1

    def test_remove_field(self):
        doc = {"a": 1, "b": 2}
        ops = [{"op": "remove", "path": "/b"}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert "b" not in result
        assert len(applied) == 1

    def test_nested_replace(self):
        doc = {"outer": {"inner": "old"}}
        ops = [{"op": "replace", "path": "/outer/inner", "value": "new"}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert result["outer"]["inner"] == "new"

    def test_array_index(self):
        doc = {"items": ["a", "b", "c"]}
        ops = [{"op": "replace", "path": "/items/1", "value": "B"}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert result["items"][1] == "B"

    def test_array_add_at_end(self):
        doc = {"items": [1, 2]}
        ops = [{"op": "add", "path": "/items/-", "value": 3}]
        result, applied, skipped = _apply_json_patch(doc, ops)
        assert result["items"] == [1, 2, 3]

    def test_empty_path_skipped(self):
        doc = {"a": 1}
        ops = [{"op": "replace", "path": "", "value": "x"}]
        _, applied, skipped = _apply_json_patch(doc, ops)
        assert len(applied) == 0
        assert len(skipped) == 1

    def test_invalid_path_skipped(self):
        doc = {"a": 1}
        ops = [{"op": "replace", "path": "/nonexistent/deep", "value": "x"}]
        _, applied, skipped = _apply_json_patch(doc, ops)
        assert len(applied) == 0
        assert len(skipped) == 1

    def test_unsupported_op_skipped(self):
        doc = {"a": 1}
        ops = [{"op": "move", "path": "/a", "value": "x"}]
        _, applied, skipped = _apply_json_patch(doc, ops)
        assert len(applied) == 0
        assert len(skipped) == 1

    def test_does_not_mutate_original(self):
        doc = {"a": 1}
        ops = [{"op": "replace", "path": "/a", "value": 2}]
        result, _, _ = _apply_json_patch(doc, ops)
        assert doc["a"] == 1  # original unchanged
        assert result["a"] == 2


# ===========================================================================
# Unit tests: Pydantic validation
# ===========================================================================


class TestValidateCsrdDocuments:
    """Tests for _validate_csrd_documents()."""

    def test_valid_kb_passes(self):
        with open(_KB_PATH) as f:
            kb = json.load(f)
        errors, warnings = _validate_csrd_documents(kb)
        assert errors == []

    def test_invalid_document_id_fails(self):
        kb = {
            "csrd_reporting_requirements": [
                {
                    "document_id": "bad-id",  # invalid pattern
                    "document_type": "Test",
                    "governing_standards": ["ESRS"],
                    "mandatory": True,
                    "frequency": {"cadence": "annual", "collections_per_year": 1, "trigger": "end_of_year"},
                    "timeframe": {"period_covered": "full_financial_year"},
                    "company_applicability": [
                        {"csrd_phase": i, "label": f"Phase {i}"} for i in range(1, 5)
                    ],
                    "content": {},
                }
            ]
        }
        errors, _ = _validate_csrd_documents(kb)
        assert len(errors) > 0
        assert any("bad-id" in e for e in errors)

    def test_extra_fields_produce_warnings(self):
        with open(_KB_PATH) as f:
            kb = json.load(f)
        # Inject an extra field into the first document
        kb["csrd_reporting_requirements"][0]["_test_extra_field"] = True
        _, warnings = _validate_csrd_documents(kb)
        assert any("_test_extra_field" in w for w in warnings)


# ===========================================================================
# Unit tests: CELEX ID configuration
# ===========================================================================


class TestGetTrackedCelexIds:
    """Tests for get_tracked_celex_ids()."""

    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CSRD_CELEX_IDS", None)
            ids = get_tracked_celex_ids()
        assert "32022L2464" in ids
        assert "32023R2772" in ids

    def test_from_env(self):
        with patch.dict(os.environ, {"CSRD_CELEX_IDS": "AAA,BBB,CCC"}):
            ids = get_tracked_celex_ids()
        assert ids == ["AAA", "BBB", "CCC"]

    def test_empty_env_falls_back(self):
        with patch.dict(os.environ, {"CSRD_CELEX_IDS": "  "}):
            ids = get_tracked_celex_ids()
        assert "32022L2464" in ids


# ===========================================================================
# Unit tests: Metadata read/write
# ===========================================================================


class TestMetadata:
    """Tests for read_meta() / _write_meta()."""

    def test_read_missing_returns_empty(self, clean_meta):
        assert read_meta() == {}

    def test_write_and_read(self, clean_meta):
        data = {"last_update_utc": "2026-01-01T00:00:00+00:00", "last_result": "success"}
        _write_meta(data)
        assert _META_PATH.exists()
        result = read_meta()
        assert result["last_result"] == "success"


# ===========================================================================
# Integration tests: KBUpdater.run_update()
# ===========================================================================


class TestKBUpdaterRunUpdate:
    """Tests for the full update pipeline with mocked HTTP + Claude."""

    def _run_mocked_update(self, kb_snapshot, clean_meta, clean_backups, clean_audit, *, dry_run=False):
        """Helper: run a mocked update and return the result."""
        mock_client = _make_mock_anthropic_client([
            MOCK_ANALYSIS_RESPONSE,
            MOCK_AFFECTED_SECTIONS,
            MOCK_PATCH_OPS,
        ])

        with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            updater = KBUpdater()
            result = updater.run_update("32025L1234", dry_run=dry_run)
        return result

    def test_successful_update(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        result = self._run_mocked_update(kb_snapshot, clean_meta, clean_backups, clean_audit)
        assert result["success"] is True
        assert result["celex_id"] == "32025L1234"
        assert result["applied"] >= 1
        assert result["validation_errors"] == []
        assert result["dry_run"] is False

    def test_creates_backup(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        self._run_mocked_update(kb_snapshot, clean_meta, clean_backups, clean_audit)
        assert _BACKUP_DIR.exists()
        backups = list(_BACKUP_DIR.glob("master_requirements_*.json"))
        assert len(backups) == 1

    def test_writes_audit_trail(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        self._run_mocked_update(kb_snapshot, clean_meta, clean_backups, clean_audit)
        assert _AUDIT_DIR.exists()
        audits = list(_AUDIT_DIR.glob("audit_*_32025L1234.txt"))
        assert len(audits) == 1
        content = audits[0].read_text()
        assert "AUDIT LOG" in content
        assert "32025L1234" in content

    def test_updates_metadata(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        self._run_mocked_update(kb_snapshot, clean_meta, clean_backups, clean_audit)
        meta = read_meta()
        assert meta["last_result"] == "success"
        assert "32025L1234" in meta["last_celex_ids_checked"]
        assert meta["applied_patches"] >= 1

    def test_dry_run_does_not_write(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        original_content = _KB_PATH.read_text()
        result = self._run_mocked_update(
            kb_snapshot, clean_meta, clean_backups, clean_audit, dry_run=True
        )
        assert result["success"] is True
        assert result["dry_run"] is True
        # KB file should be unchanged
        assert _KB_PATH.read_text() == original_content
        # No backup created
        assert not _BACKUP_DIR.exists()

    def test_concurrent_update_rejected(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        """Second concurrent run should be rejected with an error."""
        from tools.kb_updater import _update_lock

        # Simulate a lock being held
        _update_lock.acquire()
        try:
            mock_client = _make_mock_anthropic_client([])
            with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
                 patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
                updater = KBUpdater()
                result = updater.run_update("32025L1234")
            assert result["success"] is False
            assert "already in progress" in result["error"]
        finally:
            _update_lock.release()

    def test_eurlex_failure_returns_error(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        """If EUR-Lex fetch fails, the update returns an error."""
        def _failing_httpx_get(url, **kwargs):
            raise ConnectionError("Network unreachable")

        mock_client = _make_mock_anthropic_client([])
        with patch("tools.kb_updater.httpx.get", side_effect=_failing_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            updater = KBUpdater()
            result = updater.run_update("32025L1234")
        assert result["success"] is False
        assert "error" in result


# ===========================================================================
# Safety: validation gate prevents bad writes
# ===========================================================================


class TestValidationGate:
    """Verify that failed Pydantic validation does NOT overwrite the KB."""

    def test_invalid_patch_rejected(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        """A patch that makes the KB invalid should be rejected."""
        # Patch that would break document_id format (invalid pattern)
        bad_patch = json.dumps([
            {
                "op": "replace",
                "path": "/csrd_reporting_requirements/0/document_id",
                "value": "INVALID_ID_FORMAT",  # violates ^[A-Z0-9]+-[0-9]{3}$ pattern
            }
        ])

        mock_client = _make_mock_anthropic_client([
            MOCK_ANALYSIS_RESPONSE,
            MOCK_AFFECTED_SECTIONS,
            bad_patch,
        ])

        original_content = _KB_PATH.read_text()

        with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            updater = KBUpdater()
            result = updater.run_update("32025L1234")

        assert result["success"] is False
        assert len(result["validation_errors"]) > 0
        # KB file should be UNCHANGED
        assert _KB_PATH.read_text() == original_content

    def test_audit_trail_written_on_failure(self, kb_snapshot, clean_meta, clean_backups, clean_audit):
        """Even if validation fails, an audit trail should be written."""
        bad_patch = json.dumps([
            {
                "op": "replace",
                "path": "/csrd_reporting_requirements/0/document_id",
                "value": "INVALID_ID_FORMAT",
            }
        ])

        mock_client = _make_mock_anthropic_client([
            MOCK_ANALYSIS_RESPONSE,
            MOCK_AFFECTED_SECTIONS,
            bad_patch,
        ])

        with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            updater = KBUpdater()
            updater.run_update("32025L1234")

        assert _AUDIT_DIR.exists()
        audits = list(_AUDIT_DIR.glob("audit_*.txt"))
        assert len(audits) >= 1
        content = audits[0].read_text()
        assert "SCHEMA ERRORS" in content


# ===========================================================================
# Backup rotation
# ===========================================================================


class TestBackupRotation:
    """Tests for backup rotation (keep last 10)."""

    def test_rotation_keeps_max_backups(self, kb_snapshot, clean_backups):
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        # Create 12 backups (2 more than max)
        for i in range(12):
            ts = f"2026010{i:02d}_000000"
            path = _BACKUP_DIR / f"master_requirements_{ts}.json"
            path.write_text("{}")

        # Trigger one more backup via the static method
        KBUpdater._create_backup("20260199_999999")

        backups = sorted(_BACKUP_DIR.glob("master_requirements_*.json"))
        assert len(backups) <= _MAX_BACKUPS


# ===========================================================================
# Cache invalidation
# ===========================================================================


class TestCacheInvalidation:
    """Tests for reload_requirements() cache invalidation."""

    def test_load_returns_cached_instance(self):
        load_requirements.cache_clear()
        kb1 = load_requirements()
        kb2 = load_requirements()
        assert kb1 is kb2

    def test_reload_returns_fresh_instance(self):
        load_requirements.cache_clear()
        kb1 = load_requirements()
        kb2 = reload_requirements()
        # After reload, should be a new instance (even if data is same)
        assert kb1 is not kb2
        assert isinstance(kb2, CSRDReportingRequirements)

    def test_reload_picks_up_file_changes(self, kb_snapshot):
        """After modifying the file and calling reload, new data appears."""
        load_requirements.cache_clear()
        kb1 = load_requirements()
        original_desc = kb1.description

        # Modify the file in place
        with open(_KB_PATH) as f:
            data = json.load(f)
        data["_description"] = "MODIFIED FOR TEST"
        with open(_KB_PATH, "w") as f:
            json.dump(data, f, indent=2)

        # Without reload, cache returns stale data
        kb_stale = load_requirements()
        assert kb_stale.description == original_desc

        # With reload, fresh data appears
        kb_fresh = reload_requirements()
        assert kb_fresh.description == "MODIFIED FOR TEST"


# ===========================================================================
# FastAPI endpoint tests
# ===========================================================================


class TestKBEndpoints:
    """Tests for /kb/update and /kb/status endpoints."""

    @pytest.fixture(autouse=True)
    def _setup(self, clean_meta):
        """Ensure clean metadata for each test."""
        pass

    def test_kb_status_empty(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/kb/status")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_kb_status_with_data(self):
        _write_meta({
            "last_update_utc": "2026-02-20T12:00:00+00:00",
            "last_result": "success",
            "applied_patches": 3,
        })
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/kb/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_result"] == "success"

    def test_kb_update_endpoint(self, kb_snapshot, clean_backups, clean_audit):
        """POST /kb/update should trigger an update and return results."""
        mock_client = _make_mock_anthropic_client([
            MOCK_ANALYSIS_RESPONSE,
            MOCK_AFFECTED_SECTIONS,
            MOCK_PATCH_OPS,
        ])

        with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/kb/update?celex_id=32025L1234")

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["celex_id"] == "32025L1234"
        assert data["results"][0]["success"] is True

    def test_kb_update_default_celex_ids(self, kb_snapshot, clean_backups, clean_audit):
        """POST /kb/update without celex_id uses tracked defaults."""
        # Need enough mock responses for 2 CELEX IDs (default tracked set)
        mock_client = _make_mock_anthropic_client([
            MOCK_ANALYSIS_RESPONSE, MOCK_AFFECTED_SECTIONS, MOCK_PATCH_OPS,
            MOCK_ANALYSIS_RESPONSE, MOCK_AFFECTED_SECTIONS, MOCK_PATCH_OPS,
        ])

        with patch("tools.kb_updater.httpx.get", side_effect=_mock_httpx_get), \
             patch("tools.kb_updater.anthropic.Anthropic", return_value=mock_client):
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/kb/update")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2  # both default CELEX IDs


# ===========================================================================
# Background scheduler logic
# ===========================================================================


class TestSchedulerLogic:
    """Tests for the background scheduler staleness detection."""

    def test_stale_detection_over_7_days(self, clean_meta):
        """Metadata older than 7 days should be considered stale."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        _write_meta({"last_update_utc": old_date, "last_result": "success"})
        meta = read_meta()
        last_dt = datetime.fromisoformat(meta["last_update_utc"])
        age_days = (datetime.now(timezone.utc) - last_dt).days
        assert age_days > 7

    def test_fresh_detection_under_7_days(self, clean_meta):
        """Metadata under 7 days old should be considered fresh."""
        recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        _write_meta({"last_update_utc": recent_date, "last_result": "success"})
        meta = read_meta()
        last_dt = datetime.fromisoformat(meta["last_update_utc"])
        age_days = (datetime.now(timezone.utc) - last_dt).days
        assert age_days <= 7

    def test_no_metadata_triggers_update(self, clean_meta):
        """Missing metadata file means no previous update — should trigger."""
        meta = read_meta()
        assert meta.get("last_update_utc") is None


# ===========================================================================
# SSE "rules up to date" event
# ===========================================================================


class TestRulesUpToDateSSE:
    """Tests that _run_graph emits a 'rules up to date' log event."""

    def test_run_graph_emits_kb_status(self, clean_meta):
        """The first SSE event in a graph run should confirm KB freshness."""
        _write_meta({
            "last_update_utc": "2026-02-20T12:00:00+00:00",
            "last_result": "success",
        })

        # Use the real _AuditJob class and real register/unregister so
        # emit_log can find the callback and push events to job.events
        from main import _AuditJob, _run_graph

        job = _AuditJob()

        with patch("main.graph") as mock_graph:
            mock_graph.invoke.return_value = {
                "pipeline_trace": [],
                "final_result": None,
            }

            state = {
                "audit_id": "test-sse-kb-001",
                "mode": "free_text",
                "logs": [],
                "pipeline_trace": [],
            }

            _run_graph("test-sse-kb-001", state, job)

        # First event should be the KB freshness confirmation
        assert len(job.events) >= 1
        first_event = job.events[0]
        assert first_event["type"] == "log"
        assert first_event["agent"] == "system"
        assert "Regulatory rules verified up to date" in first_event["message"]
        assert "2026-02-20" in first_event["message"]


# ===========================================================================
# Regression: existing knowledge_base.py functions still work
# ===========================================================================


class TestKnowledgeBaseRegression:
    """Ensure that the new reload_requirements() didn't break anything."""

    def test_load_requirements_returns_valid_model(self):
        load_requirements.cache_clear()
        kb = load_requirements()
        assert isinstance(kb, CSRDReportingRequirements)

    def test_determine_size_category_still_works(self):
        from tools.knowledge_base import determine_size_category
        assert determine_size_category(600, 50_000_000, 25_000_000) == "large_pie"
        assert determine_size_category(300, 50_000_000, 15_000_000) == "large"
        assert determine_size_category(50, 5_000_000, 2_000_000) == "sme"

    def test_get_applicable_requirements_still_works(self):
        from tools.knowledge_base import get_applicable_requirements
        reqs = get_applicable_requirements("large_pie", 2024)
        assert len(reqs) > 0
        e1_ids = [r["disclosure_id"] for r in reqs if r["document_id"] == "E1-001"]
        assert "E1-1" in e1_ids

    def test_reload_then_load_consistent(self):
        """After reload, load_requirements should return the reloaded data."""
        kb_reloaded = reload_requirements()
        kb_cached = load_requirements()
        assert kb_reloaded is kb_cached

    def test_caching_behavior_preserved(self):
        """Multiple calls to load_requirements return the same object."""
        load_requirements.cache_clear()
        kb1 = load_requirements()
        kb2 = load_requirements()
        assert kb1 is kb2


# ===========================================================================
# Atomic file write safety
# ===========================================================================


class TestAtomicWrite:
    """Tests for atomic file write mechanics."""

    def test_atomic_write_updates_file(self, kb_snapshot):
        with open(_KB_PATH) as f:
            original = json.load(f)

        modified = dict(original)
        modified["_description"] = "ATOMIC WRITE TEST"
        KBUpdater._atomic_write_kb(modified)

        with open(_KB_PATH) as f:
            written = json.load(f)
        assert written["_description"] == "ATOMIC WRITE TEST"

    def test_atomic_write_no_temp_file_left(self, kb_snapshot):
        with open(_KB_PATH) as f:
            original = json.load(f)
        KBUpdater._atomic_write_kb(original)
        # No .tmp file should remain
        assert not _KB_PATH.with_suffix(".tmp").exists()
