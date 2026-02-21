"""
LangGraph state machine — Iteration 1 skeleton with echo/stub nodes.

Graph topology (strictly sequential — no conditional branching in v1):
  START → extractor → fetcher → auditor → consultant → END

Each node reads from AuditState and writes only to its own output keys.
Iteration 1: all nodes are pass-through stubs that log and write dummy values.
Iterations 3–6 will swap in real Claude API calls without changing this topology.
"""

from langgraph.graph import END, StateGraph

from agents.auditor import auditor_node
from agents.consultant import consultant_node
from agents.extractor import extractor_node
from agents.fetcher import fetcher_node
from state import AuditState

workflow = StateGraph(AuditState)

workflow.add_node("extractor", extractor_node)
workflow.add_node("fetcher", fetcher_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("consultant", consultant_node)

workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "fetcher")
workflow.add_edge("fetcher", "auditor")
workflow.add_edge("auditor", "consultant")
workflow.add_edge("consultant", END)

graph = workflow.compile()
