import pytest

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter


@pytest.fixture(autouse=True)
def isolate_in_process_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    rate_limiter.clear_all()
