"""
Pydantic Models for MITRE ATT&CK Entities
==========================================
Typed representations of STIX 2.1 objects parsed from ATT&CK data.
"""

from pydantic import BaseModel, Field
from typing import Optional


class AttackEntity(BaseModel):
    """Base model for all ATT&CK entities (graph nodes)."""
    stix_id: str = Field(..., description="STIX 2.1 ID (e.g., attack-pattern--xxx)")
    attack_id: str = Field(default="", description="ATT&CK ID (e.g., T1566)")
    name: str = Field(..., description="Entity name")
    description: str = Field(default="", description="Full description text")
    node_label: str = Field(..., description="Graph node label (e.g., Technique)")
    url: str = Field(default="", description="ATT&CK URL")
    domain: str = Field(default="enterprise", description="ATT&CK domain")


class Technique(AttackEntity):
    node_label: str = "Technique"
    platforms: list[str] = Field(default_factory=list)
    is_subtechnique: bool = False
    tactics: list[str] = Field(default_factory=list, description="Kill chain phase names")


class Group(AttackEntity):
    node_label: str = "Group"
    aliases: list[str] = Field(default_factory=list)


class Software(AttackEntity):
    node_label: str = "Software"
    aliases: list[str] = Field(default_factory=list)
    software_type: str = Field(default="", description="'tool' or 'malware'")


class Campaign(AttackEntity):
    node_label: str = "Campaign"
    aliases: list[str] = Field(default_factory=list)


class Mitigation(AttackEntity):
    node_label: str = "Mitigation"


class Tactic(AttackEntity):
    node_label: str = "Tactic"
    shortname: str = Field(default="", description="e.g., 'initial-access'")


class DataSource(AttackEntity):
    node_label: str = "DataSource"
    platforms: list[str] = Field(default_factory=list)


class DataComponent(AttackEntity):
    node_label: str = "DataComponent"


class AttackRelationship(BaseModel):
    """Represents a STIX relationship between two ATT&CK entities."""
    stix_id: str = Field(..., description="Relationship STIX ID")
    relationship_type: str = Field(..., description="e.g., 'uses', 'mitigates'")
    source_ref: str = Field(..., description="Source entity STIX ID")
    target_ref: str = Field(..., description="Target entity STIX ID")
    source_name: str = Field(default="", description="Source entity name (for embedding)")
    target_name: str = Field(default="", description="Target entity name (for embedding)")
    description: str = Field(default="", description="Relationship description")
    edge_label: str = Field(default="", description="Graph edge label (e.g., USES)")
