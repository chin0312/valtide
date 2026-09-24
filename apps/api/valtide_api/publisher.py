"""X Layer publisher and read-only control-plane verification.

The backend publishes only the latest warmed ``RuntimeStore`` result. Contract
addresses and identifier hashes come from the public deployment manifest; the
publisher key is read from the process environment and is never returned,
logged, or persisted.
"""

from __future__ import annotations

import json
import math
import re
import time
from ast import literal_eval
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from valtide_api.config import Settings, get_settings
from valtide_api.models import EvidenceState, ValuationResult

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BYTES32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_EVIDENCE_ENUM = {
    EvidenceState.SUPPORTED: 0,
    EvidenceState.INCONCLUSIVE: 1,
    EvidenceState.CHALLENGED: 2,
}
_EVIDENCE_BY_CODE = {value: key.value for key, value in _EVIDENCE_ENUM.items()}
_POLICY_ACTION_BY_CODE = {
    0: "ALLOW",
    1: "MONITOR",
    2: "REQUIRE_REVIEW",
    3: "RESTRICT_NEW_RISK",
}
_POLICY_ACTION_CODE = {value: key for key, value in _POLICY_ACTION_BY_CODE.items()}
_REFERENCE_SOURCE = "okx_xperp_index"
_CANONICAL_ASSET_NAME = "NVDAx"
_CANONICAL_REFERENCE_NAME = "OKX_NVDA_USD_INDEX"
_CANONICAL_MODEL_VERSION = "0.2.0"
_EVIDENCE_SCHEMA = "valtide-evidence-v1"
_READBACK_ATTEMPTS = 5
_READBACK_RETRY_DELAY_SECONDS = 1.0


class PublisherError(RuntimeError):
    """Base class for safe, user-facing publisher errors."""


class PublisherNotConfigured(PublisherError):
    """Raised when required runtime configuration is absent."""


class PublishabilityError(PublisherError):
    """Raised when a result is not safe to publish."""


class StaleResultError(PublishabilityError):
    """Raised when publication would roll the registry observation backwards."""


class ChainPreflightError(PublisherError):
    """Raised when the configured chain or deployed control plane is invalid."""


class PublicationError(PublisherError):
    """Raised when a transaction cannot be submitted or confirmed."""


class ReadbackMismatchError(PublicationError):
    """Raised when the Registry does not contain the submitted payload."""


class EnforcementVerificationError(ChainPreflightError):
    """Raised when the DemoVault call does not match its configured policy."""


@dataclass(frozen=True)
class DeploymentConfig:
    """Public deployment metadata resolved from the manifest and env overrides."""

    manifest_path: Path
    network: str
    chain_id: int
    registry_address: str
    risk_guard_address: str
    demo_vault_address: str
    asset_id: str
    reference_id: str
    model_version: str
    manifest_publisher: str | None
    rpc_url: str | None


@dataclass
class PublishReceipt:
    status: str
    tx_hash: str | None
    registry_address: str
    asset_id: str
    reference_id: str
    observed_at: int
    valid_until: int
    published_at: int | None
    evidence_hash: str
    evidence_state: str
    policy_action: str
    exists: bool
    fresh: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tx_hash": self.tx_hash,
            "registry": self.registry_address,
            "asset_id": self.asset_id,
            "reference_id": self.reference_id,
            "observed_at": self.observed_at,
            "valid_until": self.valid_until,
            "published_at": self.published_at,
            "evidence_hash": self.evidence_hash,
            "evidence_state": self.evidence_state,
            "policy_action": self.policy_action,
            "exists": self.exists,
            "fresh": self.fresh,
        }


def _web3_class() -> Any:
    try:
        from web3 import Web3
    except ImportError as exc:  # pragma: no cover - CI installs the core dependency
        raise PublisherNotConfigured("web3 dependency is not installed") from exc
    return Web3


def _normalize_rpc_url(value: str | None) -> str | None:
    if not value:
        return None
    return value if "://" in value else f"https://{value}"


def _normalize_private_key(value: str) -> str:
    return value if value.startswith("0x") else f"0x{value}"


def _validate_address(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ADDRESS_RE.fullmatch(value):
        raise PublisherNotConfigured(f"deployment manifest contains an invalid {label}")
    return value


def _validate_bytes32(value: str, label: str) -> str:
    if not isinstance(value, str) or not _BYTES32_RE.fullmatch(value):
        raise PublisherNotConfigured(f"deployment manifest contains an invalid {label}")
    return value.lower()


def _keccak_bytes(data: bytes) -> str:
    Web3 = _web3_class()
    return "0x" + bytes(Web3.keccak(data)).hex()


def keccak_text(value: str) -> str:
    """Return Ethereum Keccak-256 for a UTF-8 string as a bytes32 hex value."""
    return _keccak_bytes(value.encode("utf-8"))


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublisherNotConfigured(f"deployment manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublisherNotConfigured("deployment manifest could not be read") from exc
    if not isinstance(data, dict):
        raise PublisherNotConfigured("deployment manifest must be a JSON object")
    return data


def load_deployment_config(settings: Settings | None = None) -> DeploymentConfig:
    """Resolve public deployment metadata without requiring a private key."""
    settings = settings or get_settings()
    path = settings.resolved_deployment_manifest_path
    manifest = _load_manifest(path)
    contracts = manifest.get("contracts")
    demo = manifest.get("demo")
    if not isinstance(contracts, dict) or not isinstance(demo, dict):
        raise PublisherNotConfigured("deployment manifest is missing contracts or demo metadata")

    try:
        chain_id = int(settings.xlayer_chain_id or manifest["chainId"])
        network = str(manifest["network"])
        registry_address = str(
            settings.registry_address or contracts["ValtideValidationRegistry"]
        )
        risk_guard_address = str(settings.risk_guard_address or contracts["ValtideRiskGuard"])
        demo_vault_address = str(settings.demo_vault_address or contracts["DemoCollateralVault"])
        asset_id = str(demo["assetId"])
        reference_id = str(demo["referenceId"])
        model_version = str(demo["modelVersion"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PublisherNotConfigured("deployment manifest is missing required metadata") from exc

    if chain_id <= 0:
        raise PublisherNotConfigured("deployment chain ID must be positive")
    registry_address = _validate_address(registry_address, "registry address")
    risk_guard_address = _validate_address(risk_guard_address, "risk guard address")
    demo_vault_address = _validate_address(demo_vault_address, "demo vault address")
    asset_id = _validate_bytes32(asset_id, "asset ID")
    reference_id = _validate_bytes32(reference_id, "reference ID")
    model_version = _validate_bytes32(model_version, "model version")

    # These text identities are protocol constants, while their hashes remain
    # in the manifest. This catches accidentally mixing a different deployment.
    if keccak_text(_CANONICAL_ASSET_NAME) != asset_id:
        raise PublisherNotConfigured("deployment asset ID does not match NVDAx")
    if keccak_text(_CANONICAL_REFERENCE_NAME) != reference_id:
        raise PublisherNotConfigured("deployment reference ID does not match the OKX index")
    if keccak_text(_CANONICAL_MODEL_VERSION) != model_version:
        raise PublisherNotConfigured("deployment model version does not match quant 0.2.0")

    manifest_publisher = manifest.get("publisher")
    if manifest_publisher is not None:
        manifest_publisher = _validate_address(str(manifest_publisher), "publisher")

    return DeploymentConfig(
        manifest_path=path,
        network=network,
        chain_id=chain_id,
        registry_address=registry_address,
        risk_guard_address=risk_guard_address,
        demo_vault_address=demo_vault_address,
        asset_id=asset_id,
        reference_id=reference_id,
        model_version=model_version,
        manifest_publisher=manifest_publisher,
        rpc_url=_normalize_rpc_url(settings.xlayer_rpc_url),
    )


def _to_e8(value: float) -> int:
    if not math.isfinite(value) or value <= 0:
        raise PublishabilityError("attestation prices must be finite and positive")
    return round(value * 1e8)


def _to_bps(value: float) -> int:
    if not math.isfinite(value):
        raise PublishabilityError("reference deviation must be finite")
    converted = round(value * 100)
    if converted < -(2**31) or converted > 2**31 - 1:
        raise PublishabilityError("reference deviation does not fit int32")
    return converted


def _timestamp_seconds(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PublishabilityError("valuation timestamp must be timezone-aware")
    seconds = int(value.astimezone(UTC).timestamp())
    if seconds <= 0:
        raise PublishabilityError("valuation timestamp must be positive")
    return seconds


def canonical_evidence_bytes(result: ValuationResult, config: DeploymentConfig) -> bytes:
    """Build deterministic evidence bytes; no publication time is included."""
    timestamp = result.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "schema": _EVIDENCE_SCHEMA,
        "asset": result.asset,
        "assetId": config.asset_id,
        "referenceId": config.reference_id,
        "timestamp": timestamp,
        "marketState": result.market_state,
        "lastTrustedReference": result.last_trusted_reference,
        "tokenPrice": result.token_price,
        "externalConstructedReference": result.external_constructed_reference,
        "fairValue": result.valtide_fair_value,
        "lowerBound": result.fair_value_lower,
        "upperBound": result.fair_value_upper,
        "coverageTarget": result.interval_coverage_target,
        "observedTokenMovePct": result.observed_token_move_pct,
        "modelImpliedMovePct": result.model_implied_move_pct,
        "residualPremiumDiscountPct": result.residual_premium_discount_pct,
        "referenceUnderTest": result.reference_under_test,
        "referenceUnderTestSource": result.reference_under_test_source,
        "referenceUnderTestTs": (
            result.reference_under_test_ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if result.reference_under_test_ts is not None
            else None
        ),
        "referenceUnderTestAgeSeconds": result.reference_under_test_age_seconds,
        "referenceDeviationPct": result.reference_deviation_pct,
        "standardizedDeviation": result.standardized_deviation,
        "evidenceState": result.evidence_state.value,
        "reasonCodes": sorted(result.reason_codes),
        "confidence": result.confidence,
        "modelId": result.model_id,
        "modelVersion": result.model_version,
        "intervalSemantics": result.interval_semantics,
        "intervalCalibrationType": result.interval_calibration_type,
        "intervalCalibrationSource": result.interval_calibration_source,
        "referenceAgeSeconds": result.reference_age_seconds,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def build_attestation(
    result: ValuationResult,
    config: DeploymentConfig | None = None,
    validity_seconds: int | None = None,
    current_chain_timestamp: int | None = None,
) -> dict[str, Any]:
    """Translate a warmed result into the Registry input fields."""
    config = config or load_deployment_config()
    settings = get_settings()
    validity_seconds = (
        settings.publish_validity_seconds if validity_seconds is None else validity_seconds
    )
    if validity_seconds <= 0:
        raise PublishabilityError("publication validity must be positive")
    if result.asset != _CANONICAL_ASSET_NAME:
        raise PublishabilityError(f"asset '{result.asset}' is not publishable")
    if result.reference_under_test is None or result.reference_deviation_pct is None:
        raise PublishabilityError("reference-under-test observation is required")
    if result.reference_under_test_source != _REFERENCE_SOURCE:
        raise PublishabilityError("reference-under-test source is not the configured OKX index")
    if result.evidence_state not in _EVIDENCE_ENUM:
        raise PublishabilityError("unknown evidence state")
    if not (
        math.isfinite(result.fair_value_lower)
        and math.isfinite(result.fair_value_upper)
        and result.fair_value_lower <= result.valtide_fair_value <= result.fair_value_upper
    ):
        raise PublishabilityError("fair-value bounds are invalid")

    observed_at = _timestamp_seconds(result.timestamp)
    if current_chain_timestamp is not None and observed_at > current_chain_timestamp:
        raise PublishabilityError("valuation timestamp is ahead of the chain")
    valid_until = observed_at + int(validity_seconds)
    if current_chain_timestamp is not None and valid_until <= current_chain_timestamp:
        raise PublishabilityError("valuation validity window is already stale")

    evidence_hash = _keccak_bytes(canonical_evidence_bytes(result, config))
    model_version = keccak_text(result.model_version)
    if model_version != config.model_version:
        raise PublishabilityError("valuation model version does not match the deployment")

    return {
        "assetId": config.asset_id,
        "referenceId": config.reference_id,
        "referencePriceE8": _to_e8(result.reference_under_test),
        "fairValueE8": _to_e8(result.valtide_fair_value),
        "lowerBoundE8": _to_e8(result.fair_value_lower),
        "upperBoundE8": _to_e8(result.fair_value_upper),
        "referenceDeviationBps": _to_bps(result.reference_deviation_pct),
        "evidenceState": _EVIDENCE_ENUM[result.evidence_state],
        "evidenceHash": evidence_hash,
        "modelVersion": model_version,
        "observedAt": observed_at,
        "validUntil": valid_until,
    }


def _bytes32(value: str) -> bytes:
    return bytes.fromhex(value[2:])


def _hex_value(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith("0x") else f"0x{value}"
    return "0x" + bytes(value).hex()


def _field(value: Any, name: str, index: int) -> Any:
    if isinstance(value, dict):
        return value[name]
    try:
        return getattr(value, name)
    except AttributeError:
        return value[index]


def _load_abi(name: str) -> list[dict[str, Any]]:
    try:
        text = (
            resources.files("valtide_api.abis")
            .joinpath(f"{name}.json")
            .read_text(encoding="utf-8")
        )
        return json.loads(text)
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError) as exc:
        raise PublisherNotConfigured(f"bundled ABI unavailable for {name}") from exc


def _custom_error_abi(contract_name: str, error_name: str) -> tuple[str, list[str]]:
    for entry in _load_abi(contract_name):
        if entry.get("type") == "error" and entry.get("name") == error_name:
            input_types = [str(item["type"]) for item in entry.get("inputs", [])]
            signature = f"{error_name}({','.join(input_types)})"
            selector = "0x" + bytes(_web3_class().keccak(text=signature)[:4]).hex()
            return selector, input_types
    raise PublisherNotConfigured(f"bundled ABI is missing error {error_name}")


def _revert_data_candidates(value: Any, seen: set[int] | None = None) -> list[bytes]:
    """Extract possible ABI revert payloads from Web3 exception shapes."""
    seen = seen or set()
    if value is None or id(value) in seen:
        return []
    seen.add(id(value))
    if isinstance(value, bytes | bytearray | memoryview):
        return [bytes(value)]
    if isinstance(value, str):
        candidates: list[bytes] = []
        for match in re.finditer(r"0x[0-9a-fA-F]{8,}", value):
            encoded = match.group(0)
            if len(encoded) % 2 == 0:
                candidates.append(bytes.fromhex(encoded[2:]))
        for match in re.finditer(r"b(['\"])(.*?)\1", value):
            try:
                parsed = literal_eval(match.group(0))
            except (SyntaxError, ValueError):
                continue
            if isinstance(parsed, bytes):
                candidates.append(parsed)
        return candidates
    if isinstance(value, dict):
        candidates = []
        for key in ("data", "result", "return", "error", "originalError"):
            if key in value:
                candidates.extend(_revert_data_candidates(value[key], seen))
        return candidates
    if isinstance(value, list | tuple):
        candidates = []
        for item in value:
            candidates.extend(_revert_data_candidates(item, seen))
        return candidates
    return []


def _exception_revert_data(exc: Exception) -> list[bytes]:
    values: list[Any] = [getattr(exc, "data", None), getattr(exc, "message", None)]
    values.extend(getattr(exc, "args", ()))
    candidates: list[bytes] = []
    seen: set[int] = set()
    for value in values:
        candidates.extend(_revert_data_candidates(value, seen))
    return candidates


def _is_expected_demo_vault_revert(
    exc: Exception,
    w3: Any,
    evaluation: dict[str, Any],
) -> bool:
    selector, input_types = _custom_error_abi(
        "DemoCollateralVault", "NewExposureNotAllowed"
    )
    selector_bytes = bytes.fromhex(selector[2:])
    for data in _exception_revert_data(exc):
        if not data.startswith(selector_bytes):
            continue
        try:
            decoded = w3.codec.decode(input_types, data[4:])
        except Exception:
            continue
        evidence_code, policy_code, exists, fresh = decoded
        if (
            int(evidence_code) == evaluation["evidence_state_code"]
            and int(policy_code) == evaluation["policy_action_code"]
            and bool(exists) == evaluation["exists"]
            and bool(fresh) == evaluation["fresh"]
        ):
            return True
    return False


def _checksum(w3: Any, address: str) -> str:
    return w3.to_checksum_address(address)


def _contracts(w3: Any, config: DeploymentConfig) -> tuple[Any, Any, Any]:
    return (
        w3.eth.contract(
            address=_checksum(w3, config.registry_address),
            abi=_load_abi("ValtideValidationRegistry"),
        ),
        w3.eth.contract(
            address=_checksum(w3, config.risk_guard_address),
            abi=_load_abi("ValtideRiskGuard"),
        ),
        w3.eth.contract(
            address=_checksum(w3, config.demo_vault_address),
            abi=_load_abi("DemoCollateralVault"),
        ),
    )


def connect_web3(config: DeploymentConfig) -> Any:
    if not config.rpc_url:
        raise PublisherNotConfigured("set XLAYER_RPC_URL for X Layer access")
    Web3 = _web3_class()
    w3 = Web3(Web3.HTTPProvider(config.rpc_url, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        raise ChainPreflightError("could not connect to the configured X Layer RPC")
    return w3


def _code_present(w3: Any, address: str) -> bool:
    code = w3.eth.get_code(_checksum(w3, address))
    return bool(code and bytes(code) != b"\x00" and bytes(code) != b"")


def _read_latest(registry: Any, config: DeploymentConfig) -> dict[str, Any]:
    attestation, exists = registry.functions.getLatest(
        _bytes32(config.asset_id), _bytes32(config.reference_id)
    ).call()
    result: dict[str, Any] = {"exists": bool(exists)}
    if not exists:
        return result
    result.update(
        {
            "referenceId": _hex_value(_field(attestation, "referenceId", 0)).lower(),
            "referencePriceE8": int(_field(attestation, "referencePriceE8", 1)),
            "fairValueE8": int(_field(attestation, "fairValueE8", 2)),
            "lowerBoundE8": int(_field(attestation, "lowerBoundE8", 3)),
            "upperBoundE8": int(_field(attestation, "upperBoundE8", 4)),
            "referenceDeviationBps": int(_field(attestation, "referenceDeviationBps", 5)),
            "evidenceState": int(_field(attestation, "evidenceState", 6)),
            "evidenceHash": _hex_value(_field(attestation, "evidenceHash", 7)).lower(),
            "modelVersion": _hex_value(_field(attestation, "modelVersion", 8)).lower(),
            "observedAt": int(_field(attestation, "observedAt", 9)),
            "publishedAt": int(_field(attestation, "publishedAt", 10)),
            "validUntil": int(_field(attestation, "validUntil", 11)),
        }
    )
    return result


def decode_evaluation(values: Any) -> dict[str, Any]:
    """Decode RiskGuard's enum/bool tuple into API-safe semantic fields."""
    evidence_code, policy_code, exists, fresh = values
    evidence_code = int(evidence_code)
    policy_code = int(policy_code)
    if evidence_code not in _EVIDENCE_BY_CODE or policy_code not in _POLICY_ACTION_BY_CODE:
        raise ChainPreflightError("deployed control plane returned an unknown enum value")
    return {
        "evidence_state_code": evidence_code,
        "evidence_state": _EVIDENCE_BY_CODE[evidence_code],
        "policy_action_code": policy_code,
        "policy_action": _POLICY_ACTION_BY_CODE[policy_code],
        "exists": bool(exists),
        "fresh": bool(fresh),
    }


def _read_evaluation(w3: Any, guard: Any, config: DeploymentConfig) -> dict[str, Any]:
    values = guard.functions.evaluateFor(
        _checksum(w3, config.demo_vault_address),
        _bytes32(config.asset_id),
        _bytes32(config.reference_id),
    ).call()
    return decode_evaluation(values)


def _verify_deployment(w3: Any, config: DeploymentConfig) -> tuple[Any, Any, Any, dict[str, Any]]:
    try:
        chain_id = int(w3.eth.chain_id)
    except Exception as exc:
        raise ChainPreflightError("could not read the connected chain ID") from exc
    if chain_id != config.chain_id:
        raise ChainPreflightError(
            f"connected chain ID {chain_id} does not match deployment chain ID {config.chain_id}"
        )
    for label, address in (
        ("registry", config.registry_address),
        ("risk guard", config.risk_guard_address),
        ("demo vault", config.demo_vault_address),
    ):
        if not _code_present(w3, address):
            raise ChainPreflightError(f"no bytecode found at the deployed {label} address")

    registry, guard, vault = _contracts(w3, config)
    if guard.functions.registry().call().lower() != config.registry_address.lower():
        raise ChainPreflightError("RiskGuard is linked to a different Registry")
    if vault.functions.riskGuard().call().lower() != config.risk_guard_address.lower():
        raise ChainPreflightError("DemoVault is linked to a different RiskGuard")
    if _hex_value(vault.functions.assetId().call()).lower() != config.asset_id:
        raise ChainPreflightError("DemoVault asset ID does not match the deployment manifest")
    if _hex_value(vault.functions.referenceId().call()).lower() != config.reference_id:
        raise ChainPreflightError("DemoVault reference ID does not match the deployment manifest")

    policy_values, configured = guard.functions.getPolicy(
        _checksum(w3, config.demo_vault_address),
        _bytes32(config.asset_id),
        _bytes32(config.reference_id),
    ).call()
    if not configured:
        raise ChainPreflightError("DemoVault policy is not configured")
    policy = {
        "max_age": int(_field(policy_values, "maxAge", 0)),
        "on_supported_code": int(_field(policy_values, "onSupported", 1)),
        "on_inconclusive_code": int(_field(policy_values, "onInconclusive", 2)),
        "on_challenged_code": int(_field(policy_values, "onChallenged", 3)),
        "on_stale_code": int(_field(policy_values, "onStale", 4)),
    }
    for key in (
        "on_supported_code",
        "on_inconclusive_code",
        "on_challenged_code",
        "on_stale_code",
    ):
        if policy[key] not in _POLICY_ACTION_BY_CODE:
            raise ChainPreflightError("deployed policy returned an unknown action value")
    policy.update(
        {
            "on_supported": _POLICY_ACTION_BY_CODE[policy["on_supported_code"]],
            "on_inconclusive": _POLICY_ACTION_BY_CODE[policy["on_inconclusive_code"]],
            "on_challenged": _POLICY_ACTION_BY_CODE[policy["on_challenged_code"]],
            "on_stale": _POLICY_ACTION_BY_CODE[policy["on_stale_code"]],
        }
    )
    return registry, guard, vault, policy


def read_control_plane(
    settings: Settings | None = None,
    web3_client: Any | None = None,
) -> dict[str, Any]:
    """Read deployment, linkage, policy, and current evaluation state."""
    settings = settings or get_settings()
    config = load_deployment_config(settings)
    w3 = web3_client or connect_web3(config)
    registry, guard, _vault, policy = _verify_deployment(w3, config)
    latest = _read_latest(registry, config)
    evaluation = _read_evaluation(w3, guard, config)
    return {
        "configured": True,
        "deployed": True,
        "network": config.network,
        "chain_id": config.chain_id,
        "registry": config.registry_address,
        "risk_guard": config.risk_guard_address,
        "demo_vault": config.demo_vault_address,
        "asset_id": config.asset_id,
        "reference_id": config.reference_id,
        "model_version": config.model_version,
        "policy": policy,
        "attestation": latest if latest["exists"] else None,
        "registry_fresh": bool(
            registry.functions.isFresh(
                _bytes32(config.asset_id), _bytes32(config.reference_id)
            ).call()
        ),
        **evaluation,
    }


def classify_existing_attestation(
    existing: dict[str, Any], candidate: dict[str, Any]
) -> str:
    """Classify an idempotent publication without touching the chain."""
    if not existing.get("exists"):
        return "publish"
    current_observed = int(existing["observedAt"])
    candidate_observed = int(candidate["observedAt"])
    if candidate_observed < current_observed:
        raise StaleResultError("result is older than the Registry's latest observation")
    if (
        candidate_observed == current_observed
        and existing.get("evidenceHash", "").lower() == candidate["evidenceHash"].lower()
        and int(existing.get("validUntil", 0)) >= int(candidate["validUntil"])
    ):
        return "already_published"
    return "publish"


def _receipt_from_state(
    status: str,
    tx_hash: str | None,
    config: DeploymentConfig,
    candidate: dict[str, Any],
    state: dict[str, Any],
) -> PublishReceipt:
    attestation = state.get("attestation")
    published_at = None
    if isinstance(attestation, dict) and attestation.get("publishedAt"):
        published_at = int(attestation["publishedAt"])
    return PublishReceipt(
        status=status,
        tx_hash=tx_hash,
        registry_address=config.registry_address,
        asset_id=config.asset_id,
        reference_id=config.reference_id,
        observed_at=int(candidate["observedAt"]),
        valid_until=int(candidate["validUntil"]),
        published_at=published_at,
        evidence_hash=str(candidate["evidenceHash"]),
        evidence_state=_EVIDENCE_BY_CODE[int(candidate["evidenceState"])],
        policy_action=str(state["policy_action"]),
        exists=bool(state["exists"]),
        fresh=bool(state["fresh"]),
    )


def _tx_hash(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith("0x") else f"0x{value}"
    encoded = value.hex()
    return encoded if encoded.startswith("0x") else f"0x{encoded}"


def _assert_readback(candidate: dict[str, Any], actual: dict[str, Any]) -> None:
    for key in (
        "referenceId",
        "referencePriceE8",
        "fairValueE8",
        "lowerBoundE8",
        "upperBoundE8",
        "referenceDeviationBps",
        "evidenceState",
        "evidenceHash",
        "modelVersion",
        "observedAt",
        "validUntil",
    ):
        expected = candidate[key]
        found = actual.get(key)
        if isinstance(expected, str):
            expected = expected.lower()
            found = str(found).lower()
        if found != expected:
            raise ReadbackMismatchError(f"Registry read-back mismatch for {key}")
    if not actual.get("exists") or int(actual.get("publishedAt", 0)) <= 0:
        raise ReadbackMismatchError("Registry read-back did not contain a published attestation")


def _readback_after_publish(
    registry: Any, config: DeploymentConfig, candidate: dict[str, Any]
) -> dict[str, Any]:
    """Read back a mined write, tolerating a short RPC read-after-write lag."""
    for attempt in range(_READBACK_ATTEMPTS):
        actual = _read_latest(registry, config)
        try:
            _assert_readback(candidate, actual)
            return actual
        except ReadbackMismatchError:
            observed_at = int(actual.get("observedAt", 0) or 0)
            if attempt == _READBACK_ATTEMPTS - 1 or (
                actual.get("exists") and observed_at >= int(candidate["observedAt"])
            ):
                raise
            time.sleep(_READBACK_RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable")


def publish(
    result: ValuationResult,
    settings: Settings | None = None,
    web3_client: Any | None = None,
) -> PublishReceipt:
    """Publish one warmed result, with preflight, monotonicity, and read-back."""
    settings = settings or get_settings()
    if not settings.xlayer_rpc_url or not settings.publisher_private_key:
        raise PublisherNotConfigured(
            "set XLAYER_RPC_URL and PUBLISHER_PRIVATE_KEY for X Layer publication"
        )
    config = load_deployment_config(settings)
    w3 = web3_client or connect_web3(config)
    registry, _guard, _vault, _policy = _verify_deployment(w3, config)
    try:
        signer = w3.eth.account.from_key(_normalize_private_key(settings.publisher_private_key))
    except Exception as exc:
        raise PublisherNotConfigured("PUBLISHER_PRIVATE_KEY is invalid") from exc

    publisher_address = _checksum(w3, signer.address)
    if not registry.functions.isPublisher(publisher_address).call():
        raise ChainPreflightError("publisher signer is not authorized by the Registry")
    try:
        chain_timestamp = int(w3.eth.get_block("latest")["timestamp"])
    except Exception as exc:
        raise ChainPreflightError("could not read the latest X Layer block") from exc

    candidate = build_attestation(
        result,
        config=config,
        validity_seconds=settings.publish_validity_seconds,
        current_chain_timestamp=chain_timestamp,
    )
    existing = _read_latest(registry, config)
    decision = classify_existing_attestation(existing, candidate)
    if decision == "already_published":
        state = read_control_plane(settings=settings, web3_client=w3)
        return _receipt_from_state("already_published", None, config, candidate, state)

    input_tuple = (
        _bytes32(candidate["referenceId"]),
        int(candidate["referencePriceE8"]),
        int(candidate["fairValueE8"]),
        int(candidate["lowerBoundE8"]),
        int(candidate["upperBoundE8"]),
        int(candidate["referenceDeviationBps"]),
        int(candidate["evidenceState"]),
        _bytes32(candidate["evidenceHash"]),
        _bytes32(candidate["modelVersion"]),
        int(candidate["observedAt"]),
        int(candidate["validUntil"]),
    )
    try:
        nonce = w3.eth.get_transaction_count(publisher_address, "pending")
        gas_price = int(w3.eth.gas_price)
        transaction = registry.functions.publishValidation(
            _bytes32(candidate["assetId"]), input_tuple
        ).build_transaction(
            {
                "from": publisher_address,
                "nonce": nonce,
                "chainId": config.chain_id,
                "gasPrice": gas_price,
            }
        )
        transaction["gas"] = int(w3.eth.estimate_gas(transaction) * 1.2)
        signed = w3.eth.account.sign_transaction(
            transaction, private_key=_normalize_private_key(settings.publisher_private_key)
        )
        raw_transaction = getattr(signed, "raw_transaction", None)
        if raw_transaction is None:
            raw_transaction = signed.rawTransaction
        tx_hash = _tx_hash(w3.eth.send_raw_transaction(raw_transaction))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    except PublishabilityError:
        raise
    except Exception as exc:
        raise PublicationError("X Layer publication transaction failed") from exc

    status = (
        receipt.get("status")
        if isinstance(receipt, dict)
        else getattr(receipt, "status", None)
    )
    if int(status or 0) != 1:
        raise PublicationError("X Layer publication transaction reverted")
    _readback_after_publish(registry, config, candidate)
    state = read_control_plane(settings=settings, web3_client=w3)
    return _receipt_from_state("published", tx_hash, config, candidate, state)


def check_demo_vault_enforcement(
    settings: Settings | None = None,
    web3_client: Any | None = None,
) -> dict[str, Any]:
    """Simulate the DemoVault gate and compare it with RiskGuard evaluation."""
    settings = settings or get_settings()
    config = load_deployment_config(settings)
    w3 = web3_client or connect_web3(config)
    _registry, guard, vault, _policy = _verify_deployment(w3, config)
    evaluation = _read_evaluation(w3, guard, config)
    policy_action_code = evaluation["policy_action_code"]
    if policy_action_code in (0, 1):
        try:
            returned_action = int(vault.functions.requestNewExposure(1).call())
        except Exception as exc:
            raise EnforcementVerificationError(
                "DemoVault enforcement call failed unexpectedly"
            ) from exc
        if returned_action != policy_action_code:
            raise EnforcementVerificationError(
                "DemoVault returned an unexpected policy action"
            )
        return {
            "expected_revert": False,
            "reverted": False,
            "returned_action_code": returned_action,
            "passed": True,
            **evaluation,
        }

    try:
        vault.functions.requestNewExposure(1).call()
    except Exception as exc:
        if not _is_expected_demo_vault_revert(exc, w3, evaluation):
            raise EnforcementVerificationError(
                "DemoVault did not return the expected NewExposureNotAllowed error"
            ) from exc
        return {
            "expected_revert": True,
            "reverted": True,
            "returned_action_code": None,
            "passed": True,
            **evaluation,
        }
    raise EnforcementVerificationError(
        "DemoVault permitted new exposure under a restrictive policy"
    )
