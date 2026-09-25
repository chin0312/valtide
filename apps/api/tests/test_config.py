import pytest
from pydantic import ValidationError

from valtide_api.config import Settings


def test_settlement_settings_have_production_safe_defaults():
    settings = Settings(_env_file=None)

    assert settings.live_settlement_grace_seconds == 60
    assert settings.live_settlement_max_attempts == 5
    assert settings.live_settlement_retry_delay_seconds == 15


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("live_settlement_grace_seconds", -1),
        ("live_settlement_max_attempts", 0),
        ("live_settlement_retry_delay_seconds", -1),
    ],
)
def test_settlement_settings_reject_invalid_values(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
