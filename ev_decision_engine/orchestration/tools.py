"""Constrained remediation tools. Each one only SIMULATES its action."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool


@tool
def restart_pod(node: str) -> str:
    """Restart the pod running on a single node."""
    return f"[simulated] restarted {node}"


@tool
def drain_node(node: str) -> str:
    """Drain workloads off a single node so it can be taken out of service."""
    return f"[simulated] drained {node}"


@tool
def reroute_traffic(node_pair: str) -> str:
    """Reroute traffic around a failed link between two nodes, e.g. 'node-3 <-> node-7'."""
    return f"[simulated] rerouted traffic around {node_pair}"


@tool
def scale_service(region: str) -> str:
    """Scale up the service in a region to absorb load."""
    return f"[simulated] scaled service in {region}"


REMEDIATION_TOOLS: list[BaseTool] = [restart_pod, drain_node, reroute_traffic, scale_service]
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in REMEDIATION_TOOLS}
