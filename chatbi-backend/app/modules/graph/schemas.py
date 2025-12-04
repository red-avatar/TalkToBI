from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class GraphNode(BaseModel):
    id: str
    label: str  # 'Table' or 'Column'
    properties: Dict[str, Any] = {}

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}

class GraphVisualizationData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class CreateRelationshipRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_type: str = Field("JOIN_ON", description="Relationship type, e.g. JOIN_ON")
    properties: Dict[str, Any] = Field(default_factory=dict)

class DeleteRelationshipRequest(BaseModel):
    relationship_id: str # Neo4j internal ID is often easiest for deletion

class CreateNodeRequest(BaseModel):
    label: str
    properties: Dict[str, Any]
