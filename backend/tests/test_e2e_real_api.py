"""
End-to-end test with REAL Claude API — structured_document mode using ASML XHTML.

Parses the XHTML file from docs/, runs the full LangGraph pipeline
(extractor → scorer → advisor) with a live Anthropic API key.

Now includes narrative sustainability extraction from untagged HTML text.

Requires:
  - ANTHROPIC_API_KEY set in backend/.env or environment
  - docs/asml-2024-12-31-en.xhtml present

Run:
  cd backend && python -m pytest tests/test_e2e_real_api.py -v -s
"""

import os
import sys

import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv

load_dotenv(os.path.join(_backend_dir, ".env"))

from graph import graph
from schemas import ComplianceResult, CompanyInputs
from state import AuditState
from tools.report_parser import extract_xhtml_to_json, parse_report

# Path to the XHTML file
XHTML_PATH = os.path.join(_backend_dir, "..", "docs", "asml-2024-12-31-en.xhtml")


@pytest.fixture(scope="module")
def parsed_report():
    """Parse the ASML XHTML file once for all tests in this module."""
    assert os.path.exists(XHTML_PATH), f"XHTML file not found: {XHTML_PATH}"
    raw_json = extract_xhtml_to_json(XHTML_PATH)
    cleaned, esrs_data, taxonomy_data, narrative_sections = parse_report(
        raw_json, file_path=XHTML_PATH
    )
    print(f"\n[XHTML parsed] {len(cleaned['facts'])} clean facts, "
          f"{len(esrs_data['facts'])} ESRS facts, "
          f"{len(taxonomy_data['facts'])} taxonomy facts, "
          f"{len(narrative_sections)} narrative sections "
          f"({sum(s['char_count'] for s in narrative_sections)} chars)")
    return cleaned, esrs_data, taxonomy_data, narrative_sections


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping real API test",
)
class TestRealAPIStructuredDocument:
    """Full pipeline with real Claude API calls using ASML XHTML data."""

    def test_full_pipeline_real_api(self, parsed_report):
        """extractor → scorer → advisor with real Claude API and ASML XHTML."""
        cleaned, esrs_data, taxonomy_data, narrative_sections = parsed_report

        state: AuditState = {
            "audit_id": "real-api-asml-001",
            "mode": "structured_document",
            "report_json": cleaned,
            "esrs_data": esrs_data,
            "taxonomy_data": taxonomy_data,
            "narrative_sections": narrative_sections,
            "entity_id": "ASML Holding N.V.",
            "company_inputs": CompanyInputs(
                number_of_employees=43000,
                revenue_eur=27_559_000_000.0,
                total_assets_eur=40_634_000_000.0,
                reporting_year=2024,
            ),
            "logs": [],
            "pipeline_trace": [],
        }

        print("\n[Running pipeline] extractor → scorer → advisor (real API)...")
        result = graph.invoke(state)

        # -- Final result exists and is valid --
        assert "final_result" in result, "Pipeline did not produce a final_result"
        final = result["final_result"]
        assert isinstance(final, ComplianceResult)

        print(f"\n[Result] audit_id={final.audit_id}, mode={final.mode}")
        print(f"[Result] company={final.company.name}, sector={final.company.sector}")
        print(f"[Result] score={final.score.overall}/100, "
              f"size_category={final.score.size_category}")
        print(f"[Result] disclosed={final.score.disclosed_count}, "
              f"partial={final.score.partial_count}, "
              f"missing={final.score.missing_count}")
        print(f"[Result] {len(final.recommendations)} recommendations")

        # -- Basic structural checks --
        assert final.audit_id == "real-api-asml-001"
        assert final.mode == "structured_document"
        assert final.schema_version == "3.0"

        # -- Company meta populated by Claude --
        assert final.company.name is not None
        assert len(final.company.name) > 0

        # -- Score computed --
        assert 0 <= final.score.overall <= 100
        assert final.score.size_category != ""
        assert final.score.applicable_standards_count > 0

        # -- Recommendations generated --
        assert len(final.recommendations) > 0
        for rec in final.recommendations:
            assert rec.priority in ("critical", "high", "moderate", "low")

        # -- Pipeline trace --
        assert final.pipeline.total_duration_ms > 0
        assert len(final.pipeline.agents) == 3
        agent_names = [a.agent for a in final.pipeline.agents]
        assert agent_names == ["extractor", "scorer", "advisor"]
        for agent in final.pipeline.agents:
            assert agent.status == "completed"
            print(f"[Trace] {agent.agent}: {agent.duration_ms}ms")

        # -- Check internal state for financial_context and esrs_claims --
        esrs_claims = result.get("esrs_claims", {})
        print(f"[Result] {len(esrs_claims)} ESRS claims in state")
        assert len(esrs_claims) > 0, "Extractor should have produced ESRS claims"

        # With narrative extraction, we expect significantly more claims
        for claim_id, claim in esrs_claims.items():
            print(f"  {claim_id}: {claim.data_point} = {claim.disclosed_value} "
                  f"(conf={claim.confidence}, xbrl={claim.xbrl_concept})")

        financial_context = result.get("financial_context")
        if financial_context is not None:
            fc = financial_context
            capex = fc.capex_total_eur if hasattr(fc, 'capex_total_eur') else fc.get('capex_total_eur')
            rev = fc.revenue_eur if hasattr(fc, 'revenue_eur') else fc.get('revenue_eur')
            print(f"[Result] financial_context: capex={capex}, revenue={rev}")

        # -- Logs accumulated --
        logs = result.get("logs", [])
        assert len(logs) > 0
        agents_in_logs = set(log["agent"] for log in logs)
        assert "extractor" in agents_in_logs
        assert "scorer" in agents_in_logs
        assert "advisor" in agents_in_logs
        print(f"[Logs] {len(logs)} total log entries from {agents_in_logs}")
