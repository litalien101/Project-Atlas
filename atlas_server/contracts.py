"""Runtime validation against Atlas's canonical ontology and schema registry."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

from .world import WORLD_ENTITY_IDS, REGION_ENTITY_ID, world_manifest


class ContractError(ValueError):
    """A game entity, relationship, or event violates the Atlas contract."""


class AtlasContracts:
    def __init__(self, specs_dir: Path):
        try:
            self.ontology = self._read_yaml(specs_dir / "atlas-ontology.yaml")
            self.registry = self._read_yaml(specs_dir / "atlas-schema-registry.yaml")
        except OSError as exc:
            raise ContractError(f"Atlas contract file is unavailable: {exc.filename}") from exc

        self.entities = self.ontology.get("entities")
        self.registered_types = set(self.registry.get("registered_schemas", []))
        self.relationships = self.ontology.get("relationships", {})
        if not isinstance(self.entities, dict) or not isinstance(self.relationships, dict):
            raise ContractError("Atlas ontology must define entity and relationship mappings")
        if not self.registered_types:
            raise ContractError("Atlas schema registry has no registered entity types")
        self.entity_by_id: dict[str, dict[str, Any]] = {}
        self.relationships_seeded: list[dict[str, str]] = []
        self._validate_registration()
        self._load_world_manifest()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as stream:
                value = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ContractError(f"Invalid YAML in {path.name}: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractError(f"{path.name} must contain a YAML mapping")
        return value

    def _validate_registration(self) -> None:
        missing = self.registered_types - self.entities.keys()
        if missing:
            raise ContractError(f"Registered types missing from ontology: {sorted(missing)}")
        for relation_type, definition in self.relationships.items():
            if not isinstance(definition, dict):
                raise ContractError(f"Relationship {relation_type!r} must be a mapping")
            source_types = definition.get("source_types")
            target_types = definition.get("target_types")
            if not isinstance(source_types, list) or not source_types:
                raise ContractError(f"Relationship {relation_type!r} needs source types")
            if not isinstance(target_types, list) or not target_types:
                raise ContractError(f"Relationship {relation_type!r} needs target types")
            for entity_type in [*source_types, *target_types]:
                if entity_type not in self.registered_types:
                    raise ContractError(
                        f"Relationship {relation_type!r} references unregistered type {entity_type!r}"
                    )

    def _load_world_manifest(self) -> None:
        entities, relationships = world_manifest()
        for entity in entities:
            self.validate_entity(entity)
            entity_id = entity["id"]
            if entity_id in self.entity_by_id:
                raise ContractError(f"Duplicate world entity ID: {entity_id}")
            self.entity_by_id[entity_id] = entity
        for relationship in relationships:
            source = self.entity_by_id.get(relationship["source_id"])
            target = self.entity_by_id.get(relationship["target_id"])
            if source is None or target is None:
                raise ContractError(f"{relationship['type']} refers to a missing world entity")
            self.validate_relationship(relationship["type"], source["type"], target["type"])
            self.relationships_seeded.append(relationship)

    def validate_entity(self, entity: dict[str, Any]) -> None:
        if not isinstance(entity, dict):
            raise ContractError("Entity must be a mapping")
        missing = [field for field, definition in self.registry.get("schema_requirements", {}).items()
                   if isinstance(definition, dict) and definition.get("required") and field not in entity]
        if missing:
            raise ContractError(f"Entity is missing required fields: {', '.join(missing)}")
        entity_type = entity.get("type")
        if not isinstance(entity_type, str):
            raise ContractError("Entity type must be a registered string")
        if entity_type not in self.registered_types:
            raise ContractError(f"Entity type is not registered: {entity_type!r}")
        try:
            entity_id = str(UUID(entity["id"]))
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise ContractError("Entity id must be a UUID") from exc
        if entity_id != entity["id"]:
            raise ContractError("Entity id must use canonical UUID formatting")
        created_at = entity.get("created_at")
        if not isinstance(created_at, str):
            raise ContractError("Entity created_at must be a timezone-aware ISO-8601 timestamp")
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError("Entity created_at must be a valid ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ContractError("Entity created_at must include a timezone")
        if not self._is_subtype(entity_type, self.ontology.get("root_entity", "Entity")):
            raise ContractError(f"{entity_type!r} is not derived from the ontology root entity")
        required = self._required_fields(entity_type)
        missing_specific = required - entity.keys()
        if missing_specific:
            raise ContractError(f"{entity_type} is missing ontology fields: {sorted(missing_specific)}")

    def validate_relationship(self, relation_type: str, source_type: str, target_type: str) -> None:
        if not isinstance(relation_type, str):
            raise ContractError("Relationship type must be a declared string")
        if not isinstance(source_type, str) or not isinstance(target_type, str):
            raise ContractError("Relationship endpoints must have registered entity types")
        definition = self.relationships.get(relation_type)
        if definition is None:
            raise ContractError(f"Relationship type is not declared: {relation_type!r}")
        if not any(self._is_subtype(source_type, allowed) for allowed in definition["source_types"]):
            raise ContractError(f"{source_type} cannot be the source of {relation_type}")
        if not any(self._is_subtype(target_type, allowed) for allowed in definition["target_types"]):
            raise ContractError(f"{target_type} cannot be the target of {relation_type}")

    def validate_event(self, event: dict[str, Any], relation_type: str | None = None,
                       entity_types: dict[str, str] | None = None) -> None:
        self.validate_entity({
            "id": event["event_id"],
            "type": "Event",
            "created_at": event["occurred_at"],
            "event_type": event["event_type"],
        })
        if event.get("schema_version") != 1:
            raise ContractError("Unsupported world event schema version")
        if not event.get("actor_id") or not event.get("source_kind") or not event.get("source_identifier"):
            raise ContractError("World events require an actor and source reference")
        known_types = {entity_id: entity["type"] for entity_id, entity in self.entity_by_id.items()}
        if entity_types:
            known_types.update(entity_types)
        actor_type = known_types.get(event.get("actor_id"), "")
        creator_event = event.get("event_type") in {"EntityCreated", "RelationshipEstablished"}
        if creator_event:
            if actor_type != "Creator":
                raise ContractError("World-authoring events must be performed by a registered Creator entity")
            if event["event_type"] == "EntityCreated" and event.get("subject_id") != event.get("actor_id"):
                raise ContractError("EntityCreated subject must be the registered Creator actor")
            if event["event_type"] == "RelationshipEstablished" and event.get("subject_id") == event.get("actor_id"):
                raise ContractError("RelationshipEstablished subject must be the relationship source entity")
        elif not self._is_subtype(actor_type, "Player"):
            raise ContractError("Gameplay event actor must resolve to a registered Player entity")
        try:
            source_identifier = str(UUID(event["source_identifier"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise ContractError("World event source identifier must be a UUID") from exc
        if source_identifier != event["source_identifier"]:
            raise ContractError("World event source identifier must use canonical UUID formatting")
        if not event.get("rationale"):
            raise ContractError("World events require a rationale")
        if event.get("subject_id") not in known_types:
            raise ContractError("World event subject must resolve to a registered entity")
        if not creator_event and event.get("subject_id") != event.get("actor_id"):
            raise ContractError("The event subject must match the registered player actor")
        if event.get("object_id") is not None and event["object_id"] not in known_types:
            raise ContractError("World event object reference does not resolve to a validated entity")
        if relation_type is not None:
            source_type = known_types.get(event["subject_id"])
            target_type = known_types.get(event.get("object_id"))
            if source_type is None or target_type is None:
                raise ContractError("Relationship event refers to an entity outside the validated world")
            self.validate_relationship(relation_type, source_type, target_type)

    def _required_fields(self, entity_type: str) -> set[str]:
        required = {field for field, definition in self.registry.get("schema_requirements", {}).items()
                    if isinstance(definition, dict) and definition.get("required")}
        current: str | None = entity_type
        seen: set[str] = set()
        while current is not None:
            if current in seen:
                raise ContractError(f"Ontology inheritance cycle at {current}")
            seen.add(current)
            definition = self.entities.get(current)
            if not isinstance(definition, dict):
                raise ContractError(f"Unknown ontology entity {current!r}")
            required.update(definition.get("required", []))
            current = definition.get("parent")
        return required

    def _is_subtype(self, entity_type: str, expected_type: str) -> bool:
        current: str | None = entity_type
        seen: set[str] = set()
        while current is not None:
            if current == expected_type:
                return True
            if current in seen or current not in self.entities:
                return False
            seen.add(current)
            current = self.entities[current].get("parent")
        return False
