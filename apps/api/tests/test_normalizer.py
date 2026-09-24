"""Token-unit sanity classifier — only gross unit bugs, never economic depegs."""

from valtide_api.normalizer import is_unit_scale_suspect


def test_normal_scale_is_not_suspect():
    assert is_unit_scale_suspect(185.1, 185.0) is False


def test_moderate_depeg_is_not_suspect():
    # ~6% below the underlying is a real basis, not a unit problem.
    assert is_unit_scale_suspect(174.0, 185.0) is False
    # ~6% above.
    assert is_unit_scale_suspect(196.0, 185.0) is False


def test_cents_vs_dollars_is_suspect():
    assert is_unit_scale_suspect(1.85, 185.0) is True


def test_rebase_multiple_is_suspect():
    assert is_unit_scale_suspect(380.0, 185.0) is True  # ratio ~2.05


def test_missing_underlying_is_never_suspect():
    assert is_unit_scale_suspect(185.1, None) is False
    assert is_unit_scale_suspect(None, 185.0) is False
    assert is_unit_scale_suspect(185.1, 0.0) is False


def test_band_edges_are_inclusive_of_normal():
    # Exactly 0.5x / 2.0x are the boundary; just inside stays economic.
    assert is_unit_scale_suspect(93.0, 185.0) is False   # ratio ~0.503
    assert is_unit_scale_suspect(369.0, 185.0) is False  # ratio ~1.995
