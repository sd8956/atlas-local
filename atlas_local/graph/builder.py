from __future__ import annotations

from atlas_local.models import Confidence, GraphEdge, GraphNode
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace

RELATIONSHIP_TYPES = ["belongs_to_account", "deployed_in_region", "defined_by", "possibly_defined_by", "depends_on", "exposes", "incurs_cost", "has_owner_tag", "missing_owner", "supports_opportunity", "remediated_by_plan"]


def build_graph_for_workspace(workspace: str):
    handle = get_workspace(workspace)
    normalized = read_json(handle.path("evidence", "normalized", "normalized.json"), {"resources": [], "iac_entities": []})
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for res in normalized.get("resources", []):
        node = GraphNode(id=res["id"], kind=res["resource_type"], label=res.get("name") or res["resource_id"], scope=workspace, evidence=res.get("evidence", []), properties=res)
        nodes.append(node)
        if res.get("region"):
            region_id = f"region:{res['region']}"
            if not any(n.id == region_id for n in nodes):
                nodes.append(GraphNode(id=region_id, kind="region", label=res["region"], scope=workspace, confidence=Confidence.high))
            edges.append(GraphEdge(id=f"edge:{node.id}:region", source=node.id, target=region_id, relationship_type="deployed_in_region", confidence=Confidence.high, evidence=res.get("evidence", [])))
        owner_rel = "has_owner_tag" if any(k.lower() == "owner" for k in res.get("tags", {})) else "missing_owner"
        edges.append(GraphEdge(id=f"edge:{node.id}:{owner_rel}", source=node.id, target=f"tag:{owner_rel}", relationship_type=owner_rel, evidence=res.get("evidence", [])))
        if res["resource_type"] in {"nat_gateway", "volume", "instance", "db_instances"}:
            edges.append(GraphEdge(id=f"edge:{node.id}:cost", source=node.id, target="cost:aws", relationship_type="incurs_cost", evidence=res.get("evidence", [])))
        if res["resource_type"] == "security_group":
            perms = res.get("attributes", {}).get("IpPermissions", [])
            if any(r.get("CidrIp") == "0.0.0.0/0" for p in perms for r in p.get("IpRanges", [])):
                edges.append(GraphEdge(id=f"edge:{node.id}:exposes", source=node.id, target="internet:public", relationship_type="exposes", confidence=Confidence.high, evidence=res.get("evidence", [])))
    for ent in normalized.get("iac_entities", []):
        nodes.append(GraphNode(id=ent["id"], kind="iac_entity", label=ent["name"], scope=workspace, evidence=ent.get("evidence", []), properties=ent))
    graph = {"relationship_types": RELATIONSHIP_TYPES, "nodes": [n.model_dump(mode="json") for n in nodes], "edges": [e.model_dump(mode="json") for e in edges]}
    return write_json(handle.path("graph", "engineering-graph.json"), graph)
