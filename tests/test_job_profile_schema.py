import pytest
from pydantic import ValidationError

from config.job_profile import Axes


def test_axes_accepts_six_primary_axis_fields():
    axes = Axes(
        axis_backend=0.95,
        axis_frontend=0.05,
        axis_platform=0.75,
        axis_ai_data=0.25,
        axis_security_reliability=0.70,
        axis_product_ownership=0.35,
    )
    assert axes.axis_backend == 0.95
    assert axes.axis_product_ownership == 0.35


def test_axes_rejects_missing_field():
    with pytest.raises(ValidationError):
        Axes(  # missing axis_product_ownership
            axis_backend=0.5,
            axis_frontend=0.5,
            axis_platform=0.5,
            axis_ai_data=0.5,
            axis_security_reliability=0.5,
        )


def test_axes_does_not_have_fullstack_span_field():
    """fullstack_span is computed downstream; it must not be on the Pydantic model
    because we don't want the LLM to emit it."""
    assert "axis_fullstack_span" not in Axes.model_fields
    assert "fullstack_span" not in Axes.model_fields
