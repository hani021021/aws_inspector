import json
from urllib.parse import urlencode

import pytest

from remediation_agent import handlers


class FakeClients:
    def __init__(self):
        self.published = []
        self.decisions = []

    def __call__(self, service):
        return self

    def publish(self, **kwargs):
        self.published.append(kwargs)

    def send_task_success(self, taskToken, output):
        self.decisions.append((taskToken, json.loads(output)))


@pytest.fixture
def aws(monkeypatch):
    clients = FakeClients()
    monkeypatch.setattr(handlers.boto3, "client", clients)
    monkeypatch.setenv("APPROVAL_URL", "https://api.example/approval")
    monkeypatch.setenv("TOPIC_ARN", "arn:aws:sns:eu-north-1:123456789012:topic")
    return clients


PLAN = {
    "repository": "demo-service",
    "protectedTags": ["latest"],
    "plan": {
        "protected": ["sha256:new"],
        "first": ["sha256:old-index"],
        "then": ["sha256:old-child"],
    },
    "tags": {"sha256:new": ["latest", "1.0.5"], "sha256:old-index": ["1.0.4"]},
}


def test_request_approval_mails_the_plan_and_a_link_with_the_token(aws):
    handlers.request_approval({"taskToken": "tok/en+1", "plan": PLAN}, None)

    message = aws.published[0]["Message"]
    assert "1.0.4" in message and "latest, 1.0.5" in message
    assert "https://api.example/approval?token=tok%2Fen%2B1" in message


def test_get_only_shows_the_form(aws):
    page = handlers.approval_page(
        {"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": {"token": "a<b"}},
        None,
    )

    assert 'value="a&lt;b"' in page["body"]
    assert aws.decisions == []


def test_delete_images_refuses_when_the_repository_changed(monkeypatch):
    from remediation_agent import cleanup

    newer = [
        cleanup.RepoImage("sha256:newest", ["latest"]),
        cleanup.RepoImage("sha256:new", ["1.0.5"]),
        cleanup.RepoImage("sha256:old-index", ["1.0.4"]),
    ]
    monkeypatch.setattr(handlers.boto3, "client", lambda service: None)
    monkeypatch.setattr(handlers.cleanup, "load_images", lambda ecr, repo: newer)
    deleted = []
    monkeypatch.setattr(handlers.cleanup, "delete", lambda *args: deleted.append(args))

    with pytest.raises(RuntimeError, match="changed after the approval"):
        handlers.delete_images({"plan": PLAN}, None)
    assert deleted == []


@pytest.mark.parametrize("decision, approved", [("approve", True), ("reject", False)])
def test_post_reports_the_decision(aws, decision, approved):
    body = urlencode({"token": "tok/en+1", "decision": decision})

    handlers.approval_page({"requestContext": {"http": {"method": "POST"}}, "body": body}, None)

    assert aws.decisions == [("tok/en+1", {"approved": approved})]
