import pytest

from src.config import Settings


@pytest.fixture(scope="session")
def settings():
    return Settings()
