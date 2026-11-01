import pytest

from remediation_agent import inspector


class FakeSts:
    def __init__(self, account: str):
        self.account = account

    def get_caller_identity(self):
        return {"Account": self.account}


@pytest.fixture
def sts_account(monkeypatch):
    def use(account: str):
        monkeypatch.setattr(inspector.boto3, "client", lambda service: FakeSts(account))

    return use


def test_accepts_the_expected_account(sts_account):
    sts_account("066899194919")

    assert inspector.verify_account("066899194919") == "066899194919"


def test_refuses_any_other_account(sts_account):
    sts_account("111111111111")

    with pytest.raises(inspector.WrongAccountError, match="111111111111"):
        inspector.verify_account("066899194919")
