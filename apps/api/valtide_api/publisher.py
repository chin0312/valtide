"""X Layer publisher — commits an approved ValuationResult to the Registry.

Phase 3. Needs three things from Kai Ze (none available yet):
  - XLAYER_RPC_URL          (settings.xlayer_rpc_url)
  - the deployed ValtideValidationRegistry address
  - the contract ABI

Until those exist this module is import-safe but raises a clear error if called,
so /api/publish returns a 503 rather than crashing. The private key stays
server-side (settings.publisher_private_key) and is never logged or returned.

Mapping ValuationResult -> on-chain attestation (see ARCHITECTURE §13.1):
  referencePriceE8  = round(reference_under_test * 1e8)
  fairValueE8       = round(valtide_fair_value   * 1e8)
  lowerBoundE8/upperBoundE8, referenceDeviationBps, evidenceState (enum),
  evidenceHash, modelVersion, observedAt, publishedAt, validUntil
"""

from __future__ import annotations

from dataclasses import dataclass

from valtide_api.config import get_settings
from valtide_api.models import EvidenceState, ValuationResult

# On-chain enum ordering must match ValtideValidationRegistry.sol.
_EVIDENCE_ENUM = {
    EvidenceState.SUPPORTED: 0,
    EvidenceState.INCONCLUSIVE: 1,
    EvidenceState.CHALLENGED: 2,
}


class PublisherNotConfigured(RuntimeError):
    """Raised when X Layer config (RPC / address / ABI) is not yet available."""


@dataclass
class PublishReceipt:
    tx_hash: str
    registry_address: str


def _to_e8(x: float) -> int:
    return round(x * 1e8)


def build_attestation(result: ValuationResult) -> dict:
    """Translate a ValuationResult into the Registry's field types (pure, testable)."""
    if result.reference_under_test is None or result.reference_deviation_pct is None:
        raise PublisherNotConfigured(
            "cannot publish an attestation without a reference-under-test observation"
        )
    return {
        "referencePriceE8": _to_e8(result.reference_under_test),
        "fairValueE8": _to_e8(result.valtide_fair_value),
        "lowerBoundE8": _to_e8(result.fair_value_lower),
        "upperBoundE8": _to_e8(result.fair_value_upper),
        "referenceDeviationBps": round(result.reference_deviation_pct * 100),
        "evidenceState": _EVIDENCE_ENUM[result.evidence_state],
        "modelVersion": result.model_version,
        "observedAt": int(result.timestamp.timestamp()),
    }


def publish(result: ValuationResult) -> PublishReceipt:
    """Send the attestation to X Layer. Raises PublisherNotConfigured until wired."""
    settings = get_settings()
    if not settings.xlayer_rpc_url or not settings.publisher_private_key:
        raise PublisherNotConfigured(
            "X Layer not configured: set XLAYER_RPC_URL + PUBLISHER_PRIVATE_KEY and "
            "provide the deployed registry address/ABI (from Kai Ze)."
        )
    # Phase 3 implementation (web3.py): load ABI, build tx from build_attestation(),
    # sign with publisher_private_key, send, wait for receipt, return tx hash.
    raise PublisherNotConfigured("Registry address/ABI not yet provided by Kai Ze.")
