import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.seed_hr_manager import DEVELOPMENT_SEED_PASSWORD, resolve_seed_password


def test_development_keeps_the_existing_test_account_password() -> None:
    password, must_change = resolve_seed_password("development", None)

    assert password == DEVELOPMENT_SEED_PASSWORD
    assert must_change is False


@pytest.mark.parametrize("app_env", ["production", "staging", "", None])
def test_non_development_requires_an_explicit_password(app_env: str | None) -> None:
    with pytest.raises(ValueError, match="HR_SEED_PASSWORD is required"):
        resolve_seed_password(app_env, None)


@pytest.mark.parametrize("password", ["hr123", "admin123", "short"])
def test_non_development_rejects_known_weak_passwords(password: str) -> None:
    with pytest.raises(ValueError, match="too weak"):
        resolve_seed_password("production", password)


def test_non_development_requires_rotation_for_seeded_accounts() -> None:
    password, must_change = resolve_seed_password("production", "A-unique-passphrase-42")

    assert password == "A-unique-passphrase-42"
    assert must_change is True
