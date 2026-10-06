from types import SimpleNamespace

from fastapi.testclient import TestClient

from valtide_api.main import app
from valtide_api.publisher import PublishReceipt

client = TestClient(app)


def _receipt(status: str, tx_hash: str | None, published_at: int | None) -> PublishReceipt:
    return PublishReceipt(
        status=status,
        tx_hash=tx_hash,
        registry_address="0x" + "11" * 20,
        asset_id="0x" + "22" * 32,
        reference_id="0x" + "33" * 32,
        observed_at=100,
        valid_until=1000,
        published_at=published_at,
        evidence_hash="0x" + "44" * 32,
        evidence_state="INCONCLUSIVE",
        policy_action="REQUIRE_REVIEW",
        exists=True,
        fresh=True,
    )


def test_auto_publish_does_not_enable_manual_publish_route(monkeypatch):
    import valtide_api.routes.publish as publish_route

    monkeypatch.setattr(
        publish_route,
        "get_settings",
        lambda: SimpleNamespace(publish_enabled=False, auto_publish_enabled=True),
    )

    response = client.post("/api/publish/NVDAx")

    assert response.status_code == 503
    assert response.json()["detail"] == "publication is disabled"


def test_publish_without_warmed_result_returns_409(monkeypatch):
    import valtide_api.routes.publish as publish_route

    monkeypatch.setattr(
        publish_route, "get_settings", lambda: SimpleNamespace(publish_enabled=True)
    )
    monkeypatch.setattr(
        publish_route,
        "get_runtime_store",
        lambda: SimpleNamespace(load_runtime=lambda _asset, **_kwargs: None),
    )

    response = client.post("/api/publish/NVDAx")

    assert response.status_code == 409
    assert response.json()["detail"] == "no validation result to publish yet"


def test_publish_success_returns_structured_receipt(monkeypatch):
    import valtide_api.routes.publish as publish_route

    settings = SimpleNamespace(publish_enabled=True)
    result = object()
    monkeypatch.setattr(publish_route, "get_settings", lambda: settings)
    monkeypatch.setattr(
        publish_route,
        "get_runtime_store",
        lambda: SimpleNamespace(
            load_runtime=lambda _asset, **_kwargs: SimpleNamespace(latest_result=result)
        ),
    )

    def fake_publish(received_result, settings, *, asset):
        assert received_result is result
        assert settings is not None
        assert asset == "NVDAx"
        return _receipt("published", "0x" + "55" * 32, 777)

    monkeypatch.setattr(publish_route.publisher, "publish", fake_publish)

    response = client.post("/api/publish/NVDAx")

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["tx_hash"] == "0x" + "55" * 32
    assert response.json()["published_at"] == 777


def test_publish_already_published_returns_null_transaction(monkeypatch):
    import valtide_api.routes.publish as publish_route

    monkeypatch.setattr(
        publish_route, "get_settings", lambda: SimpleNamespace(publish_enabled=True)
    )
    monkeypatch.setattr(
        publish_route,
        "get_runtime_store",
        lambda: SimpleNamespace(
            load_runtime=lambda _asset, **_kwargs: SimpleNamespace(latest_result=object())
        ),
    )
    monkeypatch.setattr(
        publish_route.publisher,
        "publish",
        lambda _result, settings, *, asset: _receipt("already_published", None, 888),
    )

    response = client.post("/api/publish/NVDAx")

    assert response.status_code == 200
    assert response.json()["status"] == "already_published"
    assert response.json()["tx_hash"] is None
    assert response.json()["published_at"] == 888


def test_onchain_status_returns_mocked_control_plane(monkeypatch):
    import valtide_api.routes.onchain as onchain_route

    expected = {
        "chain_id": 1952,
        "exists": False,
        "fresh": False,
        "evidence_state": "INCONCLUSIVE",
        "policy_action": "REQUIRE_REVIEW",
    }
    monkeypatch.setattr(
        onchain_route.publisher,
        "read_control_plane",
        lambda *, asset: expected if asset == "NVDAx" else {},
    )

    response = client.get("/api/onchain/NVDAx")

    assert response.status_code == 200
    assert response.json() == {"asset": "NVDAx", **expected}


def test_onchain_status_rejects_unsupported_asset():
    response = client.get("/api/onchain/FOOx")

    assert response.status_code == 404


def test_onchain_status_reports_missing_deployment_for_registered_candidate():
    response = client.get("/api/onchain/SPYx")

    assert response.status_code == 503
    assert response.json()["detail"] == "ONCHAIN_NOT_CONFIGURED"


def test_onchain_route_keeps_each_asset_binding_scoped(monkeypatch):
    import valtide_api.routes.onchain as onchain_route

    expected = {
        asset: {
            "asset_id": f"asset-{asset}",
            "reference_id": f"reference-{asset}",
            "demo_vault": f"vault-{asset}",
            "policy": {"max_age": 900, "asset": asset},
            "attestation": {"asset": asset},
        }
        for asset in ("NVDAx", "SPYx", "AAPLx")
    }
    observed = []

    def fake_read_control_plane(*, asset):
        observed.append(asset)
        return expected[asset]

    monkeypatch.setattr(onchain_route, "require_api_asset", lambda asset, *_: asset)
    monkeypatch.setattr(onchain_route.publisher, "read_control_plane", fake_read_control_plane)

    for asset in ("NVDAx", "SPYx", "AAPLx"):
        response = client.get(f"/api/onchain/{asset}")
        assert response.status_code == 200
        assert response.json() == {"asset": asset, **expected[asset]}

    assert observed == ["NVDAx", "SPYx", "AAPLx"]
