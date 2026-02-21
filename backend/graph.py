"""
LangGraph state machine — dual-mode with conditional routing.

Graph topology:
  Full Audit:       START → extractor → fetcher → auditor → consultant → END
  Compliance Check: START → extractor → auditor → consultant → END  (fetcher skipped)

Conditional routing after extractor: checks state["mode"] to decide whether
to proceed to fetcher (full_audit) or skip directly to auditor (compliance_check).
"""

from langgraph.graph import END, StateGraph

from agents.auditor import auditor_node
from agents.consultant import consultant_node
from agents.extractor import extractor_node
from agents.fetcher import fetcher_node
from state import AuditState


def route_after_extractor(state: AuditState) -> str:
    """Conditional routing: skip fetcher in compliance_check mode."""
    if state.get("mode") == "compliance_check":
        return "auditor"
    return "fetcher"


workflow = StateGraph(AuditState)

workflow.add_node("extractor", extractor_node)
workflow.add_node("fetcher", fetcher_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("consultant", consultant_node)

workflow.set_entry_point("extractor")

workflow.add_conditional_edges("extractor", route_after_extractor, {
    "fetcher": "fetcher",
    "auditor": "auditor",
})

workflow.add_edge("fetcher", "auditor")
workflow.add_edge("auditor", "consultant")
workflow.add_edge("consultant", END)

graph = workflow.compile()
