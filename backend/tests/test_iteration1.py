"""
Iteration 1 Unit Tests — LangGraph Skeleton with Echo Nodes

Gate: Full graph runs without error, all 4 nodes execute in order,
      final_audit is populated with a valid CSRDAudit contract.

Tests are organised by node, followed by an end-to-end graph test.
"""

import pytest

from schemas import (
    CSRDAudit,
    CompanyMeta,
    ComplianceCost,
    ESRSClaim,
    ESRSLedgerItem,
    PipelineTrace,
    RegistrySource,
    TaxonomyAlignment,
    TaxonomyFinancials,
    TaxonomyRoadmap,
)


# ---------------------------------------------------------------------------
# Node 1 — Extractor
# ---------------------------------------------------------------------------


class TestExtractorNode:
    def test_returns_company_meta(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        assert "company_meta" in result
        assert isinstance(result["company_meta"], CompanyMeta)

    def test_company_name_reflects_entity_id(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        assert result["company_meta"].name == minimal_state["entity_id"]

    def test_returns_esrs_claims_dict(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        assert "esrs_claims" in result
        assert isinstance(result["esrs_claims"], dict)

    def test_esrs_claims_has_all_three_standards(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        assert "E1-1" in claims, "E1-1 (Transition Plan) claim missing"
        assert "E1-5" in claims, "E1-5 (Energy) claim missing"
        assert "E1-6" in claims, "E1-6 (GHG Emissions) claim missing"

    def test_esrs_claims_are_valid_pydantic_models(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        for key, claim in result["esrs_claims"].items():
            assert isinstance(claim, ESRSClaim), f"{key} is not an ESRSClaim"

    def test_esrs_claim_confidence_in_range(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        for key, claim in result["esrs_claims"].items():
            assert 0.0 <= claim.confidence <= 1.0, (
                f"{key} confidence {claim.confidence} outside 0–1 range"
            )

    def test_company_meta_fiscal_year_is_int(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        assert isinstance(result["company_meta"].fiscal_year, int)

    def test_appends_logs_with_agent_label(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        assert len(result["logs"]) > 0
        for log in result["logs"]:
            assert log["agent"] == "extractor"
            assert "msg" in log
            assert "ts" in log

    def test_appends_one_entry_to_pipeline_trace(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        extractor_entries = [t for t in result["pipeline_trace"] if t["agent"] == "extractor"]
        assert len(extractor_entries) == 1

    def test_pipeline_trace_entry_has_ms_field(self, minimal_state):
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        entry = next(t for t in result["pipeline_trace"] if t["agent"] == "extractor")
        assert "ms" in entry
        assert isinstance(entry["ms"], int)
        assert entry["ms"] >= 0

    def test_accumulates_existing_logs(self, minimal_state):
        """Node must append to existing logs, not overwrite them."""
        from agents.extractor import extractor_node

        seeded_state = {**minimal_state, "logs": [{"agent": "system", "msg": "init", "ts": 0}]}
        result = extractor_node(seeded_state)
        system_logs = [l for l in result["logs"] if l["agent"] == "system"]
        assert len(system_logs) == 1, "Existing log entries must be preserved"

    def test_does_not_modify_init_keys(self, minimal_state):
        """Node must not overwrite input-only keys."""
        from agents.extractor import extractor_node

        result = extractor_node(minimal_state)
        # management_text is an input key — must not appear in the returned dict
        assert "management_text" not in result
        assert "taxonomy_text" not in result
        assert "transition_text" not in result


# ---------------------------------------------------------------------------
# Node 2 — Fetcher
# ---------------------------------------------------------------------------


class TestFetcherNode:
    def test_returns_taxonomy_financials(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert "taxonomy_financials" in result
        assert isinstance(result["taxonomy_financials"], TaxonomyFinancials)

    def test_capex_values_are_non_negative(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        tf = result["taxonomy_financials"]
        if tf.capex_total_eur is not None:
            assert tf.capex_total_eur >= 0, "capex_total_eur must be non-negative"
        if tf.capex_green_eur is not None:
            assert tf.capex_green_eur >= 0, "capex_green_eur must be non-negative"

    def test_green_capex_does_not_exceed_total(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        tf = result["taxonomy_financials"]
        if tf.capex_total_eur and tf.capex_green_eur:
            assert tf.capex_green_eur <= tf.capex_total_eur, (
                "capex_green_eur must not exceed capex_total_eur"
            )

    def test_confidence_in_range(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert 0.0 <= result["taxonomy_financials"].confidence <= 1.0

    def test_source_document_is_taxonomy_table(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert result["taxonomy_financials"].source_document == "EU Taxonomy Table"

    def test_taxonomy_activities_is_list(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert isinstance(result["taxonomy_financials"].taxonomy_activities, list)

    def test_returns_document_source(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert "document_source" in result
        assert isinstance(result["document_source"], RegistrySource)

    def test_document_source_registry_type_is_valid(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        assert result["document_source"].registry_type in ("national", "eu_bris")

    def test_accumulates_logs_from_previous_nodes(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        extractor_logs = [l for l in result["logs"] if l["agent"] == "extractor"]
        fetcher_logs = [l for l in result["logs"] if l["agent"] == "fetcher"]
        assert len(extractor_logs) > 0, "Extractor logs must be preserved"
        assert len(fetcher_logs) > 0, "Fetcher must add its own logs"

    def test_pipeline_trace_contains_both_nodes(self, state_after_extractor):
        from agents.fetcher import fetcher_node

        result = fetcher_node(state_after_extractor)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert "extractor" in agents
        assert "fetcher" in agents


# ---------------------------------------------------------------------------
# Node 3 — Auditor
# ---------------------------------------------------------------------------


class TestAuditorNode:
    def test_returns_esrs_ledger(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        assert "esrs_ledger" in result
        assert isinstance(result["esrs_ledger"], list)
        assert len(result["esrs_ledger"]) > 0

    def test_esrs_ledger_items_are_valid_models(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        for item in result["esrs_ledger"]:
            assert isinstance(item, ESRSLedgerItem), f"Expected ESRSLedgerItem, got {type(item)}"

    def test_ledger_item_ids_are_unique(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        ids = [item.id for item in result["esrs_ledger"]]
        assert len(ids) == len(set(ids)), "Ledger item IDs must be unique"

    def test_returns_taxonomy_alignment(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        assert "taxonomy_alignment" in result
        assert isinstance(result["taxonomy_alignment"], TaxonomyAlignment)

    def test_capex_aligned_pct_in_range(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        pct = result["taxonomy_alignment"].capex_aligned_pct
        assert 0.0 <= pct <= 100.0, f"capex_aligned_pct {pct} out of 0–100 range"

    def test_taxonomy_status_matches_alignment_pct(self, state_after_fetcher):
        """Status must be consistent with the alignment percentage thresholds in the PRD."""
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        pct = result["taxonomy_alignment"].capex_aligned_pct
        status = result["taxonomy_alignment"].status
        if pct >= 60:
            assert status == "aligned"
        elif pct >= 20:
            assert status == "partially_aligned"
        else:
            assert status == "non_compliant"

    def test_taxonomy_alignment_score_matches_pct(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        assert "taxonomy_alignment_score" in result
        assert result["taxonomy_alignment_score"] == result["taxonomy_alignment"].capex_aligned_pct

    def test_returns_compliance_cost(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        assert "compliance_cost" in result
        assert isinstance(result["compliance_cost"], ComplianceCost)

    def test_compliance_cost_is_non_negative(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        assert result["compliance_cost"].projected_fine_eur >= 0

    def test_compliance_cost_basis_references_csrd(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        basis = result["compliance_cost"].basis
        assert "CSRD" in basis or "2022/2464" in basis, (
            "Compliance cost basis must reference CSRD Directive"
        )

    def test_alignment_pct_derived_from_taxonomy_financials(self, state_after_fetcher):
        """Auditor must use capex_green_eur / capex_total_eur from state."""
        from agents.auditor import auditor_node

        tf = state_after_fetcher["taxonomy_financials"]
        expected_pct = (tf.capex_green_eur / tf.capex_total_eur) * 100
        result = auditor_node(state_after_fetcher)
        actual_pct = result["taxonomy_alignment"].capex_aligned_pct
        assert abs(actual_pct - expected_pct) < 0.01, (
            f"Expected {expected_pct:.2f}%, got {actual_pct:.2f}%"
        )

    def test_all_ledger_items_have_valid_evidence_source(self, state_after_fetcher):
        from agents.auditor import auditor_node

        valid_sources = {"management_report", "taxonomy_table", "transition_plan"}
        result = auditor_node(state_after_fetcher)
        for item in result["esrs_ledger"]:
            assert item.evidence_source in valid_sources, (
                f"Invalid evidence_source: {item.evidence_source}"
            )

    def test_pipeline_trace_contains_three_nodes(self, state_after_fetcher):
        from agents.auditor import auditor_node

        result = auditor_node(state_after_fetcher)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert "extractor" in agents
        assert "fetcher" in agents
        assert "auditor" in agents


# ---------------------------------------------------------------------------
# Node 4 — Consultant
# ---------------------------------------------------------------------------


class TestConsultantNode:
    def test_returns_roadmap(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert "roadmap" in result
        assert isinstance(result["roadmap"], TaxonomyRoadmap)

    def test_roadmap_has_three_pillars(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        roadmap = result["roadmap"]
        assert roadmap.hardware is not None
        assert roadmap.power is not None
        assert roadmap.workload is not None

    def test_roadmap_alignment_increase_pct_in_valid_range(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        roadmap = result["roadmap"]
        for pillar_name, pillar in [
            ("hardware", roadmap.hardware),
            ("power", roadmap.power),
            ("workload", roadmap.workload),
        ]:
            assert 0 < pillar.alignment_increase_pct <= 100, (
                f"{pillar_name}.alignment_increase_pct {pillar.alignment_increase_pct} out of range"
            )

    def test_roadmap_priorities_are_valid(self, state_after_auditor):
        from agents.consultant import consultant_node

        valid_priorities = {"critical", "high", "moderate", "low"}
        result = consultant_node(state_after_auditor)
        roadmap = result["roadmap"]
        for pillar_name, pillar in [
            ("hardware", roadmap.hardware),
            ("power", roadmap.power),
            ("workload", roadmap.workload),
        ]:
            assert pillar.priority in valid_priorities, (
                f"{pillar_name}.priority '{pillar.priority}' is not valid"
            )

    def test_returns_final_audit(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert "final_audit" in result
        assert isinstance(result["final_audit"], CSRDAudit)

    def test_final_audit_preserves_audit_id(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert result["final_audit"].audit_id == state_after_auditor["audit_id"]

    def test_final_audit_schema_version(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert result["final_audit"].schema_version == "2.0"

    def test_final_audit_has_sources(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert len(result["final_audit"].sources) == 3, (
            "CSRDAudit must reference all 3 golden-source documents"
        )

    def test_final_audit_pipeline_has_four_agents(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        pipeline = result["final_audit"].pipeline
        assert isinstance(pipeline, PipelineTrace)
        assert len(pipeline.agents) == 4, (
            f"Expected 4 agent timings, got {len(pipeline.agents)}"
        )

    def test_final_audit_pipeline_total_duration_is_sum(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        pipeline = result["final_audit"].pipeline
        assert pipeline.total_duration_ms == sum(a.duration_ms for a in pipeline.agents)

    def test_final_audit_carries_esrs_ledger(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        assert len(result["final_audit"].esrs_ledger) == len(state_after_auditor["esrs_ledger"])

    def test_pipeline_trace_contains_all_four_nodes(self, state_after_auditor):
        from agents.consultant import consultant_node

        result = consultant_node(state_after_auditor)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        for expected in ("extractor", "fetcher", "auditor", "consultant"):
            assert expected in agents


# ---------------------------------------------------------------------------
# Schema sanity — Iteration 0 gate regression
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_csrdaudit_imports(self):
        from schemas import CSRDAudit  # noqa: F401

    def test_internal_schemas_import(self):
        from schemas import ESRSClaim, TaxonomyFinancials  # noqa: F401

    def test_company_meta_requires_name(self):
        with pytest.raises(Exception):
            CompanyMeta(lei=None, sector="X", fiscal_year=2024, jurisdiction="EU", report_title="R")

    def test_taxonomy_alignment_status_literal_validation(self):
        with pytest.raises(Exception):
            TaxonomyAlignment(capex_aligned_pct=50.0, status="invalid_status", label="x")

    def test_esrs_claim_confidence_not_validated_by_pydantic(self):
        """Confidence range is enforced by application logic, not Pydantic — confirm it accepts 0–1."""
        claim = ESRSClaim(standard="E1-1", data_point="test", confidence=0.75)
        assert claim.confidence == 0.75


# ---------------------------------------------------------------------------
# AuditState — state.py
# ---------------------------------------------------------------------------


class TestAuditState:
    def test_auditstate_imports(self):
        from state import AuditState  # noqa: F401

    def test_auditstate_is_typed_dict(self):
        from state import AuditState
        from typing import get_type_hints

        # TypedDict is just a dict at runtime; verify keys exist in annotations
        hints = get_type_hints(AuditState)
        assert "audit_id" in hints
        assert "management_text" in hints
        assert "taxonomy_text" in hints
        assert "transition_text" in hints
        assert "entity_id" in hints
        assert "esrs_claims" in hints
        assert "final_audit" in hints

    def test_auditstate_accepts_minimal_dict(self, minimal_state):
        # AuditState is total=False so all keys are optional — a partial dict is valid
        state: "AuditState" = minimal_state
        assert state["audit_id"] == "test-audit-001"


# ---------------------------------------------------------------------------
# Graph — End-to-End
# ---------------------------------------------------------------------------


class TestGraphEndToEnd:
    def test_graph_imports(self):
        from graph import graph  # noqa: F401

    def test_graph_compiles(self):
        from graph import graph

        assert graph is not None

    def test_graph_runs_end_to_end(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert result is not None

    def test_final_audit_present_in_result(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert "final_audit" in result
        assert isinstance(result["final_audit"], CSRDAudit)

    def test_all_four_nodes_executed_in_order(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert agents == ["extractor", "fetcher", "auditor", "consultant"], (
            f"Unexpected node execution order: {agents}"
        )

    def test_audit_id_propagated_to_final_audit(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert result["final_audit"].audit_id == minimal_state["audit_id"]

    def test_esrs_ledger_has_three_items(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert len(result["final_audit"].esrs_ledger) == 3

    def test_pipeline_has_four_agents(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert len(result["final_audit"].pipeline.agents) == 4

    def test_pipeline_agent_order_in_final_audit(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        names = [a.agent for a in result["final_audit"].pipeline.agents]
        assert names == ["extractor", "fetcher", "auditor", "consultant"]

    def test_all_agent_timings_are_completed(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        for agent_timing in result["final_audit"].pipeline.agents:
            assert agent_timing.status == "completed", (
                f"{agent_timing.agent} status is '{agent_timing.status}', expected 'completed'"
            )

    def test_logs_contain_entries_from_all_four_agents(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        logged_agents = {log["agent"] for log in result["logs"]}
        assert "extractor" in logged_agents
        assert "fetcher" in logged_agents
        assert "auditor" in logged_agents
        assert "consultant" in logged_agents

    def test_taxonomy_alignment_pct_is_number(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        pct = result["final_audit"].taxonomy_alignment.capex_aligned_pct
        assert isinstance(pct, float)
        assert 0.0 <= pct <= 100.0

    def test_sources_has_three_documents(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert len(result["final_audit"].sources) == 3

    def test_company_name_in_final_audit(self, minimal_state):
        from graph import graph

        result = graph.invoke(minimal_state)
        assert result["final_audit"].company.name == minimal_state["entity_id"]

    def test_graph_handles_empty_string_texts(self):
        """Graph must not crash when document texts are empty strings."""
        from graph import graph

        state = {
            "audit_id": "test-empty-docs",
            "management_text": "",
            "taxonomy_text": "",
            "transition_text": "",
            "entity_id": "EmptyCorp",
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert isinstance(result["final_audit"], CSRDAudit)

    def test_graph_handles_missing_entity_id(self):
        """Graph must not crash when entity_id is absent."""
        from graph import graph

        state = {
            "audit_id": "test-no-entity",
            "management_text": "x",
            "taxonomy_text": "x",
            "transition_text": "x",
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert isinstance(result["final_audit"], CSRDAudit)

    def test_final_audit_json_serialisable(self, minimal_state):
        """Final audit must be serialisable to JSON (as required for SSE streaming)."""
        import json
        from graph import graph

        result = graph.invoke(minimal_state)
        json_str = result["final_audit"].model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["audit_id"] == minimal_state["audit_id"]
        assert "esrs_ledger" in parsed
        assert "roadmap" in parsed
