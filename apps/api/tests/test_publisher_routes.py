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


def test_publish_disabled_returns_503(monkeypatch):
    import valtide_api.routes.publish as publish_route

    monkeypatch.setattr(
        publish_route, "get_settings", lambda: SimpleNamespace(publish_enabled=False)
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
        lambda: SimpleNamespace(load_runtime=lambda _asset: None),
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
            load_runtime=lambda _asset: SimpleNamespace(latest_result=result)
        ),
    )

    def fake_publish(received_result, settings):
        assert received_result is result
        assert settings is not None
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
            load_runtime=lambda _asset: SimpleNamespace(latest_result=object())
        ),
    )
    monkeypatch.setattr(
        publish_route.publisher,
        "publish",
        lambda _result, settings: _receipt("already_published", None, 888),
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
    monkeypatch.setattr(onchain_route.publisher, "read_control_plane", lambda: expected)

    response = client.get("/api/onchain/NVDAx")

    assert response.status_code == 200
    assert response.json() == expected


def test_onchain_status_rejects_unsupported_asset():
    response = client.get("/api/onchain/FOOx")

    assert response.status_code == 404
