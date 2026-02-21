"""
LangGraph state machine — v5.0 unified 3-agent pipeline.

Graph topology (both modes):
  START → extractor → scorer → advisor → END

No conditional routing. Linear 3-node pipeline for both
structured_document and free_text modes.
"""

from langgraph.graph import END, StateGraph

from agents.extractor import extractor_node
from agents.scorer import scorer_node
from agents.advisor import advisor_node
from state import AuditState

workflow = StateGraph(AuditState)

workflow.add_node("extractor", extractor_node)
workflow.add_node("scorer", scorer_node)
workflow.add_node("advisor", advisor_node)

workflow.set_entry_point("extractor")

workflow.add_edge("extractor", "scorer")
workflow.add_edge("scorer", "advisor")
workflow.add_edge("advisor", END)

graph = workflow.compile()
