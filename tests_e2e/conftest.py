import os

import pytest


@pytest.fixture(scope="session")
def calculadora_url() -> str:
    return os.getenv("CALCULADORA_URL", "http://localhost:8000")

@pytest.fixture(scope="session")
def visor_url() -> str:
    return os.getenv("VISOR_URL", "http://localhost:8001")