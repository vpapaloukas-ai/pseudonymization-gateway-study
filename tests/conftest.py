import pytest


@pytest.fixture(scope="session")
def shipped():
    from pgw.baseline import ShippedGateway

    return ShippedGateway()


@pytest.fixture(scope="session")
def analyzer(shipped):
    return shipped.analyzer


@pytest.fixture(scope="session")
def detector(shipped):
    from pgw.detector import ConfiguredDetector

    return ConfiguredDetector(nlp_engine=shipped.analyzer.nlp_engine)
