from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableSequence, MutableMapping, Sequence

from jsonschema import Draft202012Validator, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "contracts" / "intake_contract_v1.json"

PACK_FILES: Dict[str, str] = {
    "03": "03_Operating-Rules_v2.json",
    "04": "04_Governance+Risk-Register_v2.json",
    "05": "05_Safety+Privacy_Guardrails_v2.json",
    "08": "08_Memory-Schema_v2.json",
    "11": "11_Workflow-Pack_v2.json",
    "12": "12_Tool+Data-Registry_v2.json",
}

PLACEHOLDER_PATTERN = re.compile(
    r"(?:\bTBD\b|\bTODO\b|Operator to confirm|SET_ME)", re.IGNORECASE
)


@dataclass(frozen=True)
class MappingEntry:
    intake_field: str
    pack_file: str
    json_path: str
    value: Any
    description: str


@dataclass(frozen=True)
class DiffEntry:
    json_path: str
    before: Any
    after: Any
    reason: str


class IntakeValidationError(ValueError):
    """Raised when the intake payload fails schema validation."""


def load_contract() -> Dict[str, Any]:
    """Load and return the intake contract schema."""
    try:
        schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Intake contract not found at {CONTRACT_PATH}"
        ) from exc
    return schema


def _validator() -> Draft202012Validator:
    schema = load_contract()
    return Draft202012Validator(schema)


def validate_intake(payload: Dict[str, Any]) -> None:
    """Validate payload against the intake contract."""
    validator = _validator()

    def _sort_key(error: ValidationError) -> tuple:
        path = tuple(str(part) for part in error.absolute_path)
        return path + (error.message,)

    errors = sorted(validator.iter_errors(payload), key=_sort_key)
    if errors:
        messages = []
        for error in errors:
            location = "/".join(str(p) for p in error.absolute_path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise IntakeValidationError(
            "Intake contract validation failed:\n" + "\n".join(messages)
        )


def apply_intake(
    intake_payload: Dict[str, Any],
    build_root: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Apply intake payload to pack files under build_root.

    Returns aggregated mapping and diff reports. In dry-run mode no files are written.
    """
    validate_intake(intake_payload)

    build_root = build_root.resolve()
    if not build_root.exists():
        raise FileNotFoundError(f"Build root not found: {build_root}")

    packs_cache: Dict[str, Dict[str, Any]] = {}
    changes: Dict[str, List[DiffEntry]] = {name: [] for name in PACK_FILES.values()}
    mapping: List[MappingEntry] = []
    touched: Dict[str, bool] = {name: False for name in PACK_FILES.values()}

    def load_pack(name: str) -> Dict[str, Any]:
        if name in packs_cache:
            return packs_cache[name]
        path = build_root / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Expected pack file missing: {path}") from exc
        packs_cache[name] = data
        return data

    def record_change(
        pack_name: str,
        json_path: Sequence[str],
        before: Any,
        after: Any,
        reason: str,
        intake_field: str,
    ) -> None:
        if before == after:
            return
        _ensure_no_placeholders(after)
        path_str = ".".join(json_path)
        changes[pack_name].append(
            DiffEntry(json_path=path_str, before=before, after=after, reason=reason)
        )
        mapping.append(
            MappingEntry(
                intake_field=intake_field,
                pack_file=pack_name,
                json_path=path_str,
                value=after,
                description=reason,
            )
        )
        touched[pack_name] = True

    def update_value(pack: Dict[str, Any], path: Sequence[str], value: Any) -> None:
        cursor: Any = pack
        for key in path[:-1]:
            if isinstance(cursor, MutableMapping):
                cursor = cursor.setdefault(key, {})
            else:
                raise TypeError(
                    f"Expected mapping while navigating path {'.'.join(path)}"
                )
        last = path[-1]
        if isinstance(cursor, MutableMapping):
            cursor[last] = copy.deepcopy(value)
        else:
            raise TypeError(f"Unable to set path {'.'.join(path)} on non-mapping value")

    # Pack 03: RBAC roles
    pack03 = load_pack(PACK_FILES["03"])
    roles = list(intake_payload["rbac"]["roles"])
    before_roles = _deep_get(pack03, ("rbac", "roles"))
    record_change(
        PACK_FILES["03"],
        ("rbac", "roles"),
        copy.deepcopy(before_roles),
        roles,
        "Sync RBAC roles from intake contract.",
        "rbac.roles",
    )
    update_value(pack03, ("rbac", "roles"), roles)

    # Pack 04: risk register tags
    pack04 = load_pack(PACK_FILES["04"])
    risk_tags = _dedupe_list(intake_payload["governance"]["risk_register_tags"])
    before_risk = _deep_get(pack04, ("risk_register_tags",))
    record_change(
        PACK_FILES["04"],
        ("risk_register_tags",),
        copy.deepcopy(before_risk),
        risk_tags,
        "Align risk register tags with intake governance directives.",
        "governance.risk_register_tags",
    )
    update_value(pack04, ("risk_register_tags",), risk_tags)

    # Pack 05: PII flags and classification default
    pack05 = load_pack(PACK_FILES["05"])
    pii_flags = _dedupe_list(intake_payload["governance"]["pii_flags"])
    before_pii = _deep_get(pack05, ("pii_flags",))
    record_change(
        PACK_FILES["05"],
        ("pii_flags",),
        copy.deepcopy(before_pii),
        pii_flags,
        "Carry PII flags to guardrail pack.",
        "governance.pii_flags",
    )
    update_value(pack05, ("pii_flags",), pii_flags)

    classification = intake_payload["governance"]["classification_default"]
    before_class = _deep_get(pack05, ("data_classification", "default"))
    record_change(
        PACK_FILES["05"],
        ("data_classification", "default"),
        copy.deepcopy(before_class),
        classification,
        "Set default data classification from intake governance.",
        "governance.classification_default",
    )
    update_value(pack05, ("data_classification", "default"), classification)

    # Pack 08: memory scopes, retention, permissions, writeback rules
    pack08 = load_pack(PACK_FILES["08"])
    mem_scopes = _dedupe_list(intake_payload["memory"]["scopes"])
    before_scopes = _deep_get(pack08, ("memory_scopes",))
    record_change(
        PACK_FILES["08"],
        ("memory_scopes",),
        copy.deepcopy(before_scopes),
        mem_scopes,
        "Populate memory scopes from intake contract.",
        "memory.scopes",
    )
    update_value(pack08, ("memory_scopes",), mem_scopes)

    retention_updates = {
        scope: {"retention_days": days}
        for scope, days in intake_payload["memory"]["retention"].items()
    }
    retention = copy.deepcopy(pack08.get("retention") or {})
    for scope, cfg in retention_updates.items():
        retention[scope] = cfg
    before_retention = _deep_get(pack08, ("retention",))
    record_change(
        PACK_FILES["08"],
        ("retention",),
        copy.deepcopy(before_retention),
        retention,
        "Apply retention policy per intake memory directives.",
        "memory.retention",
    )
    update_value(pack08, ("retention",), retention)

    permissions = copy.deepcopy(pack08.get("permissions") or {})
    permissions["roles"] = copy.deepcopy(intake_payload["memory"]["permissions"])
    before_permissions = _deep_get(pack08, ("permissions", "roles"))
    record_change(
        PACK_FILES["08"],
        ("permissions", "roles"),
        copy.deepcopy(before_permissions),
        permissions["roles"],
        "Update memory permissions matrix from intake.",
        "memory.permissions",
    )
    update_value(pack08, ("permissions",), permissions)

    writeback_rules = _dedupe_list(intake_payload["memory"]["writeback_rules"])
    before_rules = _deep_get(pack08, ("writeback_rules",))
    record_change(
        PACK_FILES["08"],
        ("writeback_rules",),
        copy.deepcopy(before_rules),
        writeback_rules,
        "Enforce writeback rules from intake memory contract.",
        "memory.writeback_rules",
    )
    update_value(pack08, ("writeback_rules",), writeback_rules)

    # Pack 11: human gate actions
    pack11 = load_pack(PACK_FILES["11"])
    gate_actions = _dedupe_list(intake_payload["human_gate"]["actions"])
    before_actions = _deep_get(pack11, ("human_gate_actions",))
    record_change(
        PACK_FILES["11"],
        ("human_gate_actions",),
        copy.deepcopy(before_actions),
        gate_actions,
        "Sync workflow human gate actions from intake governance.",
        "human_gate.actions",
    )
    update_value(pack11, ("human_gate_actions",), gate_actions)

    # Pack 12: connectors and data sources
    pack12 = load_pack(PACK_FILES["12"])

    def _match_existing_connector(name: str) -> Dict[str, Any]:
        slug = _slugify(name)
        for existing in pack12.get("connectors") or []:
            if _slugify(existing.get("name", "")) == slug:
                return copy.deepcopy(existing)
            if str(existing.get("id", "")).lower() == slug:
                return copy.deepcopy(existing)
        return {"id": slug, "name": name}

    connectors = []
    for connector in sorted(
        intake_payload["connectors"], key=lambda item: item["name"]
    ):
        base = _match_existing_connector(connector["name"])
        base["name"] = connector["name"]
        base["enabled"] = connector["enabled"]
        base["scopes"] = sorted(connector["scopes"])
        base["secret_ref"] = connector["secret_ref"]
        if not base.get("id"):
            base["id"] = _slugify(connector["name"])
        connectors.append(base)
    before_connectors = _deep_get(pack12, ("connectors",))
    record_change(
        PACK_FILES["12"],
        ("connectors",),
        copy.deepcopy(before_connectors),
        connectors,
        "Map intake connectors into registry pack.",
        "connectors",
    )
    update_value(pack12, ("connectors",), connectors)

    data_sources = sorted(intake_payload["data_sources"])
    before_sources = _deep_get(pack12, ("data_sources",))
    record_change(
        PACK_FILES["12"],
        ("data_sources",),
        copy.deepcopy(before_sources),
        data_sources,
        "Register intake data sources as registry references.",
        "data_sources",
    )
    update_value(pack12, ("data_sources",), data_sources)

    changed_files = [name for name, flag in touched.items() if flag]

    if not dry_run:
        for name in changed_files:
            data = packs_cache[name]
            (build_root / name).write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    diff_report = [
        {
            "pack_file": pack_name,
            "changes": [
                {
                    "json_path": entry.json_path,
                    "before": entry.before,
                    "after": entry.after,
                    "reason": entry.reason,
                }
                for entry in changes[pack_name]
            ],
        }
        for pack_name in PACK_FILES.values()
        if changes[pack_name]
    ]

    mapping_report = [
        {
            "intake_field": entry.intake_field,
            "pack_file": entry.pack_file,
            "json_path": entry.json_path,
            "value": entry.value,
            "description": entry.description,
        }
        for entry in mapping
    ]

    return {
        "intake_version": intake_payload["intake_version"],
        "dry_run": dry_run,
        "changed_files": sorted(changed_files),
        "mapping_report": mapping_report,
        "diff_report": diff_report,
    }


def _deep_get(data: Dict[str, Any], path: Sequence[str]) -> Any:
    cursor: Any = data
    for key in path:
        if isinstance(cursor, MutableMapping) and key in cursor:
            cursor = cursor[key]
        else:
            return None
    return copy.deepcopy(cursor)


def _dedupe_list(values: Iterable[Any]) -> List[Any]:
    seen = []
    for item in values:
        if item not in seen:
            seen.append(item)
    return seen


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "connector"


def _ensure_no_placeholders(value: Any) -> None:
    if isinstance(value, str):
        if PLACEHOLDER_PATTERN.search(value):
            raise ValueError(f"Placeholder token detected in value: {value!r}")
    elif isinstance(value, MutableSequence):
        for item in value:
            _ensure_no_placeholders(item)
    elif isinstance(value, MutableMapping):
        for item in value.values():
            _ensure_no_placeholders(item)
