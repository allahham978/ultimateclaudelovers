"""
Knowledge-base updater — fetches EU directive text from EUR-Lex, uses Claude
to analyse changes and generate RFC 6902 JSON patches, applies them to
master_requirements.json, validates with Pydantic, writes an audit trail,
and invalidates the in-memory cache so subsequent scorer runs use fresh data.

Usage:
    from tools.kb_updater import KBUpdater
    updater = KBUpdater()
    result = updater.run_update("32022L2464", dry_run=False)
"""

from __future__ import annotations

import collections.abc
import copy
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import anthropic
import httpx
from pydantic import ValidationError

from data.schema import CSRDDocument, CSRDReportingRequirements

logger = logging.getLogger("kb_updater")

# ---------------------------------------------------------------------------
# Paths (relative to this file)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent  # backend/
_DATA_DIR = _ROOT / "data"
_KB_PATH = _DATA_DIR / "master_requirements.json"
_META_PATH = _DATA_DIR / "kb_update_meta.json"
_BACKUP_DIR = _DATA_DIR / "backups"
_AUDIT_DIR = _DATA_DIR / "audit_trail"
_DEBUG_DIR = _DATA_DIR / "debug"

_MAX_BACKUPS = 10

# Single-writer lock — prevents concurrent update runs
_update_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Default tracked CELEX IDs
# ---------------------------------------------------------------------------

_DEFAULT_CELEX_IDS = ["32022L2464", "32023R2772"]


def get_tracked_celex_ids() -> list[str]:
    """Read CELEX IDs from env var, falling back to defaults."""
    raw = os.environ.get("CSRD_CELEX_IDS", "")
    if raw.strip():
        return [cid.strip() for cid in raw.split(",") if cid.strip()]
    return list(_DEFAULT_CELEX_IDS)


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def read_meta() -> dict[str, Any]:
    """Read kb_update_meta.json, returning empty dict if missing."""
    if _META_PATH.exists():
        with open(_META_PATH) as f:
            return json.load(f)
    return {}


def _write_meta(meta: dict[str, Any]) -> None:
    _META_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _META_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, _META_PATH)


# ---------------------------------------------------------------------------
# Utility: safe JSON parsing from Claude output
# ---------------------------------------------------------------------------

def _safe_parse_json(raw: str) -> Any:
    """Parse JSON from Claude's response, stripping markdown fences."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = cleaned.find(open_char)
        end = cleaned.rfind(close_char)
        if start != -1 and end != -1:
            candidate = cleaned[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                for i in range(len(candidate) - 1, -1, -1):
                    if candidate[i] in ("}", "]"):
                        try:
                            return json.loads(candidate[: i + 1])
                        except json.JSONDecodeError:
                            continue
    raise ValueError(f"Could not parse JSON.\nFirst 300 chars:\n{cleaned[:300]}")


# ---------------------------------------------------------------------------
# Utility: extract KB schema shape (for Claude context)
# ---------------------------------------------------------------------------

def _extract_kb_schema(kb: dict, depth_limit: int = 3) -> Any:
    def get_schema(obj: Any, depth: int = 0) -> Any:
        if depth >= depth_limit:
            return "..."
        if isinstance(obj, dict):
            return {k: get_schema(v, depth + 1) for k, v in obj.items()}
        elif isinstance(obj, list) and obj:
            return [get_schema(obj[0], depth + 1)]
        return type(obj).__name__
    return get_schema(kb)


# ---------------------------------------------------------------------------
# JSON Patch (RFC 6902) application
# ---------------------------------------------------------------------------

def _resolve_path(obj: Any, path_parts: list[str]) -> tuple[Any, str]:
    for part in path_parts[:-1]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj, path_parts[-1]


def _apply_json_patch(
    doc: dict, operations: list[dict]
) -> tuple[dict, list[dict], list[tuple[dict, str]]]:
    doc = copy.deepcopy(doc)
    applied: list[dict] = []
    skipped: list[tuple[dict, str]] = []

    for op in operations:
        operation = op.get("op")
        path = op.get("path", "")
        value = op.get("value")
        parts = [p for p in path.strip("/").split("/") if p]

        if not parts:
            skipped.append((op, "empty path"))
            continue

        try:
            parent, key = _resolve_path(doc, parts)

            if operation == "replace":
                old_value = (
                    parent[int(key)]
                    if isinstance(parent, list)
                    else parent.get(key, "<new>")
                )
                if isinstance(parent, list):
                    parent[int(key)] = value
                else:
                    parent[key] = value
                applied.append(
                    {"op": operation, "path": path, "old_value": old_value, "new_value": value}
                )

            elif operation == "add":
                if isinstance(parent, list):
                    idx = int(key) if key != "-" else len(parent)
                    parent.insert(idx, value)
                else:
                    parent[key] = value
                applied.append(
                    {"op": operation, "path": path, "old_value": None, "new_value": value}
                )

            elif operation == "remove":
                if isinstance(parent, list):
                    old_value = parent[int(key)]
                    del parent[int(key)]
                else:
                    old_value = parent.pop(key, None)
                applied.append(
                    {"op": operation, "path": path, "old_value": old_value, "new_value": None}
                )

            else:
                skipped.append((op, f"unsupported op '{operation}'"))

        except (KeyError, IndexError, TypeError, ValueError) as e:
            skipped.append((op, str(e)))

    return doc, applied, skipped


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------

def _validate_csrd_documents(kb: dict) -> tuple[list[str], list[str]]:
    """Validate every document against the canonical Pydantic schema."""
    errors: list[str] = []
    warnings: list[str] = []
    docs = kb.get("csrd_reporting_requirements", [])

    for i, doc_dict in enumerate(docs):
        doc_id = doc_dict.get("document_id", f"index_{i}")
        try:
            CSRDDocument.model_validate(doc_dict)
        except ValidationError as e:
            for err in e.errors():
                loc = " → ".join(str(x) for x in err["loc"])
                errors.append(f"[{doc_id}] {loc}: {err['msg']}")
        except Exception as e:
            errors.append(f"[{doc_id}] Unexpected error: {e}")

    known_top_level = {
        "document_id", "document_type", "governing_standards", "mandatory",
        "mandatory_if_material", "mandatory_regardless_of_materiality", "mandatory_note",
        "frequency", "timeframe", "company_applicability", "content",
        "phase_in_reliefs", "alignment", "format", "assurance", "restatement_rules",
    }
    for i, doc_dict in enumerate(docs):
        doc_id = doc_dict.get("document_id", f"index_{i}")
        extras = set(doc_dict.keys()) - known_top_level
        if extras:
            warnings.append(
                f"[{doc_id}] Extra fields not in schema (allowed but review): {extras}"
            )

    return errors, warnings


# ===========================================================================
# KBUpdater class
# ===========================================================================


class KBUpdater:
    """Fetches EU directive text, generates JSON patches via Claude, and
    applies them to master_requirements.json with full validation and audit."""

    def __init__(self, *, debug: bool = False) -> None:
        self._client = anthropic.Anthropic()
        self._debug = debug

    # -----------------------------------------------------------------------
    # Claude helper
    # -----------------------------------------------------------------------

    def _stream_from_claude(
        self, system: str, user: str, max_tokens: int = 4096, label: str = ""
    ) -> str:
        full = ""
        logger.info("Streaming %s ...", label)
        with self._client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                full += text
        logger.info("Streaming %s done (%d chars)", label, len(full))
        return full

    # -----------------------------------------------------------------------
    # Step 1: Fetch directive text from EUR-Lex
    # -----------------------------------------------------------------------

    def _fetch_directive_text(self, celex_id: str) -> str:
        def clean_html(html: str) -> str:
            text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"&[a-z]+;", " ", text)
            text = re.sub(r"&#\d+;", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def cut_to_legal_content(text: str) -> str:
            markers = [
                r"THE EUROPEAN PARLIAMENT AND THE COUNCIL",
                r"THE COUNCIL OF THE EUROPEAN UNION",
                r"THE EUROPEAN COMMISSION",
                r"Having regard to",
                r"Whereas:",
                r"HAVE ADOPTED THIS",
                r"Article 1",
            ]
            earliest = len(text)
            for marker in markers:
                match = re.search(marker, text, re.IGNORECASE)
                if match and match.start() < earliest:
                    earliest = match.start()
            if earliest < len(text):
                logger.debug("Trimmed %d chars of boilerplate.", earliest)
                return text[earliest:]
            return text

        endpoints = [
            ("HTML", f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex_id}"),
            ("TXT", f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex_id}"),
        ]

        for label, url in endpoints:
            logger.info("Trying %s endpoint for %s ...", label, celex_id)
            try:
                r = httpx.get(url, headers={"Accept-Language": "en"}, timeout=30)
                if r.status_code == 200 and len(r.text) > 5000:
                    text = clean_html(r.text)
                    text = cut_to_legal_content(text)
                    logger.info(
                        "%s endpoint succeeded: %d chars.", label, len(text)
                    )
                    if self._debug:
                        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                        (_DEBUG_DIR / f"raw_directive_{celex_id}.txt").write_text(
                            text, encoding="utf-8"
                        )
                    return text
            except Exception as e:
                logger.warning("%s endpoint failed: %s", label, e)

        raise RuntimeError(f"All EUR-Lex endpoints failed for {celex_id}.")

    # -----------------------------------------------------------------------
    # Step 2: Analyse directive
    # -----------------------------------------------------------------------

    def _analyse_directive(self, raw_text: str) -> dict:
        system = (
            "You are a senior EU regulatory lawyer. Analyse the directive text and "
            "extract a structured summary.\n"
            "Return ONLY a JSON object — no markdown, no prose, no backticks:\n"
            "{\n"
            '  "directive_title": "full official title",\n'
            '  "celex_id": "string",\n'
            '  "publication_date": "YYYY-MM-DD",\n'
            '  "effective_date": "YYYY-MM-DD",\n'
            '  "implementation_deadline": "YYYY-MM-DD or null",\n'
            '  "amends_directives": ["CELEX IDs"],\n'
            '  "summary": "2-3 sentence plain English summary",\n'
            '  "affected_entity_types": ["list"],\n'
            '  "key_changes": [\n'
            '    {"article": "Article X", "topic": "short label", '
            '"change_description": "what changes",\n'
            '     "previous_rule": "old rule", "new_rule": "new rule"}\n'
            "  ],\n"
            '  "new_obligations": [],\n'
            '  "removed_obligations": [],\n'
            '  "amended_thresholds": [{"metric": "", "old_value": "", "new_value": ""}],\n'
            '  "implementation_deadlines": [{"obligation": "", "deadline": ""}],\n'
            '  "reporting_changes": [],\n'
            '  "scope_changes": []\n'
            "}"
        )
        raw = self._stream_from_claude(
            system,
            f"DIRECTIVE TEXT:\n{raw_text}",
            max_tokens=4096,
            label="directive analysis",
        )
        if self._debug:
            _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (_DEBUG_DIR / "directive_analysis.json").write_text(raw, encoding="utf-8")
        return _safe_parse_json(raw)

    # -----------------------------------------------------------------------
    # Step 3: Identify affected KB sections
    # -----------------------------------------------------------------------

    def _get_affected_sections(self, analysis: dict, kb_schema: Any) -> list[str]:
        system = (
            "You are an EU regulatory compliance expert.\n"
            "Given a directive analysis and KB schema, return ONLY a JSON array of "
            "top-level key names that need updating.\n"
            "Include keys for NEW sections that should be created even if not yet in "
            "the schema.\nNo prose. No markdown. No backticks."
        )
        user = (
            f"DIRECTIVE ANALYSIS:\n{json.dumps(analysis, indent=2)}\n\n"
            f"KB SCHEMA:\n{json.dumps(kb_schema, indent=2)}"
        )
        raw = self._stream_from_claude(
            system, user, max_tokens=512, label="affected sections"
        )
        if self._debug:
            _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (_DEBUG_DIR / "affected_keys.json").write_text(raw, encoding="utf-8")
        return _safe_parse_json(raw)

    # -----------------------------------------------------------------------
    # Step 4: Generate JSON Patch operations
    # -----------------------------------------------------------------------

    def _get_patch_operations(
        self, analysis: dict, relevant_sections: dict
    ) -> list[dict]:
        system = (
            "You are an EU Regulatory Compliance Agent maintaining a master "
            "requirements knowledge base.\n\n"
            "Generate RFC 6902 JSON Patch operations to update the knowledge base "
            "based on the directive analysis.\n\n"
            "SCHEMA CONSTRAINTS — your patch values must respect these:\n"
            "- csrd_phase must be 1, 2, 3, or 4 (integer)\n"
            "- first_data_collection_year: integer, minimum 2024\n"
            "- first_filing_year: integer, minimum 2025\n"
            "- first_comparative_year: integer, minimum 2023\n"
            "- opt_out_until_year: integer, minimum 2024\n"
            "- employee_threshold_min, employee_threshold_max: integer, minimum 1\n"
            "- All EUR thresholds: integer, minimum 0\n"
            "- size_criteria_required_of_3: integer 1-3\n"
            "- mandatory and mandatory_if_material are mutually exclusive\n"
            "- document_id must match pattern: ^[A-Z0-9]+-[0-9]{3}$\n"
            "- Every document must have all 4 csrd_phases (1-4) in company_applicability\n\n"
            "PATCH RULES:\n"
            '- Use "replace" to update an existing field\n'
            '- Use "add" to add a new field or entirely new top-level section\n'
            '- Use "remove" to delete a field\n'
            "- Paths use JSON Pointer: /section/array_index/field\n"
            "- Array indices are zero-based integers\n"
            "- Only generate operations for fields the directive explicitly changes\n"
            "- DO NOT reproduce entire objects or arrays — target individual fields only\n\n"
            "Return ONLY a JSON array of operations. No prose. No markdown. No backticks."
        )
        user = (
            f"DIRECTIVE ANALYSIS:\n{json.dumps(analysis, indent=2)}\n\n"
            f"CURRENT KB SECTIONS (use for correct array indices and field names):\n"
            f"{json.dumps(relevant_sections, indent=2)}"
        )

        raw = self._stream_from_claude(
            system, user, max_tokens=4096, label="patch operations"
        )
        if self._debug:
            _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (_DEBUG_DIR / "raw_patch.txt").write_text(raw, encoding="utf-8")

        try:
            ops = _safe_parse_json(raw)
        except ValueError as e:
            logger.warning("Parse failed: %s. Asking Claude to repair...", e)
            repair = self._stream_from_claude(
                "Fix this broken JSON array and return ONLY valid JSON. "
                "No prose. No markdown.",
                f"Fix:\n{raw}",
                max_tokens=4096,
                label="JSON repair",
            )
            ops = _safe_parse_json(repair)

        if self._debug:
            (_DEBUG_DIR / "parsed_patch.json").write_text(
                json.dumps(ops, indent=2), encoding="utf-8"
            )

        return ops

    # -----------------------------------------------------------------------
    # Audit trail
    # -----------------------------------------------------------------------

    def _write_audit_trail(
        self,
        celex_id: str,
        analysis: dict,
        applied_ops: list[dict],
        skipped_ops: list[tuple[dict, str]],
        validation_errors: list[str],
        timestamp: str,
    ) -> str:
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        audit_file = _AUDIT_DIR / f"audit_{timestamp}_{celex_id}.txt"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines: list[str] = []

        lines += [
            f"AUDIT LOG — {celex_id}",
            f"Directive : {analysis.get('directive_title', 'N/A')}",
            f"Run       : {now}",
            f"Source    : https://eur-lex.europa.eu/eli/dir/{celex_id}/oj",
            f"Validation: {'ERRORS — review required' if validation_errors else 'passed'}",
            "",
            "CHANGES",
            "-" * 60,
        ]

        def fmt_val(v: Any) -> str:
            if v is None:
                return "—"
            if isinstance(v, dict):
                keys = list(v.keys())[:3]
                return f"<new section: {keys}{'...' if len(v) > 3 else ''}>"
            s = str(v)
            return s if len(s) <= 60 else s[:57] + "..."

        for op in applied_ops:
            operation = op["op"]
            path = op["path"]
            old_val = op.get("old_value")
            new_val = op.get("new_value")
            if operation == "replace":
                lines.append(
                    f"CHANGED  {path}  |  {fmt_val(old_val)}  →  {fmt_val(new_val)}"
                )
            elif operation == "add":
                lines.append(f"ADDED    {path}  |  {fmt_val(new_val)}")
            elif operation == "remove":
                lines.append(f"REMOVED  {path}  |  was: {fmt_val(old_val)}")

        if not applied_ops:
            lines.append("(no changes applied)")

        if skipped_ops:
            lines += ["", "SKIPPED (could not apply)", "-" * 60]
            for op, reason in skipped_ops:
                lines.append(f"SKIPPED  {op.get('path', '?')}  |  {reason}")

        if validation_errors:
            lines += ["", "SCHEMA ERRORS", "-" * 60]
            for err in validation_errors:
                lines.append(f"ERROR    {err}")

        lines.append("")
        audit_text = "\n".join(lines)
        audit_file.write_text(audit_text, encoding="utf-8")
        logger.info("Audit trail written to %s", audit_file)
        return audit_text

    # -----------------------------------------------------------------------
    # Backup management
    # -----------------------------------------------------------------------

    @staticmethod
    def _create_backup(timestamp: str) -> Optional[Path]:
        if not _KB_PATH.exists():
            return None
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = _BACKUP_DIR / f"master_requirements_{timestamp}.json"
        backup_path.write_bytes(_KB_PATH.read_bytes())
        logger.info("Backup created: %s", backup_path.name)

        # Rotate: keep only the newest _MAX_BACKUPS
        backups = sorted(_BACKUP_DIR.glob("master_requirements_*.json"))
        while len(backups) > _MAX_BACKUPS:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.debug("Deleted old backup: %s", oldest.name)

        return backup_path

    # -----------------------------------------------------------------------
    # Atomic write
    # -----------------------------------------------------------------------

    @staticmethod
    def _atomic_write_kb(data: dict) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _KB_PATH.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _KB_PATH)
        logger.info("master_requirements.json updated atomically.")

    # -----------------------------------------------------------------------
    # Main pipeline
    # -----------------------------------------------------------------------

    def run_update(
        self, celex_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Run the full update pipeline for a single CELEX ID.

        Returns a result dict with keys:
            celex_id, applied, skipped, validation_errors, validation_warnings,
            dry_run, success
        """
        if not _update_lock.acquire(blocking=False):
            return {
                "celex_id": celex_id,
                "error": "Another update is already in progress.",
                "success": False,
            }

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        try:
            logger.info("=== KB update starting for %s ===", celex_id)

            # Step 1: Fetch directive text
            logger.info("[1/6] Fetching directive text from EUR-Lex...")
            raw_directive = self._fetch_directive_text(celex_id)

            # Step 2: Analyse directive
            logger.info("[2/6] Analysing directive...")
            analysis = self._analyse_directive(raw_directive)
            logger.info(
                "Title: %s | Changes: %d",
                analysis.get("directive_title", "N/A"),
                len(analysis.get("key_changes", [])),
            )

            # Step 3: Load KB + identify affected sections
            logger.info("[3/6] Loading KB and identifying affected sections...")
            with open(_KB_PATH) as f:
                master_kb = json.load(f)
            kb_schema = _extract_kb_schema(master_kb)
            affected_keys = self._get_affected_sections(analysis, kb_schema)
            logger.info("Affected sections: %s", affected_keys)

            # Step 4: Generate JSON Patch operations
            logger.info("[4/6] Generating JSON Patch operations...")
            relevant_sections = {
                k: master_kb[k] for k in affected_keys if k in master_kb
            }
            operations = self._get_patch_operations(analysis, relevant_sections)
            logger.info("Generated %d patch operations.", len(operations))

            # Step 5: Apply patch + validate
            logger.info("[5/6] Applying patch and validating...")
            updated_master, applied_ops, skipped_ops = _apply_json_patch(
                master_kb, operations
            )

            validation_errors, validation_warnings = _validate_csrd_documents(
                updated_master
            )

            if validation_errors:
                logger.warning(
                    "%d validation error(s) — update REJECTED.",
                    len(validation_errors),
                )
                # Write audit trail even on failure
                self._write_audit_trail(
                    celex_id, analysis, applied_ops, skipped_ops,
                    validation_errors, timestamp,
                )
                return {
                    "celex_id": celex_id,
                    "applied": len(applied_ops),
                    "skipped": len(skipped_ops),
                    "validation_errors": validation_errors,
                    "validation_warnings": validation_warnings,
                    "dry_run": dry_run,
                    "success": False,
                }

            if dry_run:
                logger.info("Dry run — skipping write.")
                return {
                    "celex_id": celex_id,
                    "applied": len(applied_ops),
                    "skipped": len(skipped_ops),
                    "validation_errors": [],
                    "validation_warnings": validation_warnings,
                    "dry_run": True,
                    "success": True,
                }

            # Step 6: Backup, write, audit, invalidate cache
            logger.info("[6/6] Writing updated KB...")
            self._create_backup(timestamp)
            self._atomic_write_kb(updated_master)

            self._write_audit_trail(
                celex_id, analysis, applied_ops, skipped_ops,
                validation_errors, timestamp,
            )

            # Invalidate knowledge_base LRU cache
            from tools.knowledge_base import reload_requirements
            reload_requirements()
            logger.info("Knowledge base cache invalidated.")

            # Update metadata
            _write_meta({
                "last_update_utc": datetime.now(timezone.utc).isoformat(),
                "last_celex_ids_checked": [celex_id],
                "last_result": "success",
                "applied_patches": len(applied_ops),
            })

            logger.info("=== KB update complete for %s ===", celex_id)
            return {
                "celex_id": celex_id,
                "applied": len(applied_ops),
                "skipped": len(skipped_ops),
                "validation_errors": [],
                "validation_warnings": validation_warnings,
                "dry_run": False,
                "success": True,
            }

        except Exception as e:
            logger.error("KB update failed for %s: %s", celex_id, e, exc_info=True)
            return {
                "celex_id": celex_id,
                "error": str(e),
                "success": False,
            }
        finally:
            _update_lock.release()
