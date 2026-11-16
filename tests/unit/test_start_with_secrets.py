import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from scripts.start_with_secrets import SecretsError, load_secrets

COMPLETE = {"DATABASE_URL": "postgresql+asyncpg://u:p@db/app", "ADMIN_API_KEY": "x" * 32}


def client_returning(secret_string: str | None) -> MagicMock:
    client = MagicMock()
    client.get_secret_value.return_value = {"SecretString": secret_string}
    return client


def test_copies_every_key_of_the_secret_into_the_environment() -> None:
    env = {"SECRETS_SOURCE": "aws", "SECRET_ID": "rag/prod"}
    client = client_returning(json.dumps({**COMPLETE, "EXTRA": 42}))

    load_secrets(env, client)

    assert env["DATABASE_URL"] == COMPLETE["DATABASE_URL"]
    assert env["EXTRA"] == "42"
    client.get_secret_value.assert_called_once_with(SecretId="rag/prod")


def test_requires_a_secret_id() -> None:
    with pytest.raises(SecretsError, match="SECRET_ID is required"):
        load_secrets({"SECRETS_SOURCE": "aws"}, client_returning("{}"))


def test_fails_fast_when_the_secret_cannot_be_read() -> None:
    client = MagicMock()
    client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}}, "GetSecretValue"
    )
    with pytest.raises(SecretsError, match='Could not read secret "missing"'):
        load_secrets({"SECRETS_SOURCE": "aws", "SECRET_ID": "missing"}, client)


def test_names_the_missing_required_keys() -> None:
    client = client_returning(json.dumps({"DATABASE_URL": "postgresql+asyncpg://x"}))
    with pytest.raises(SecretsError, match="missing required keys: ADMIN_API_KEY"):
        load_secrets({"SECRETS_SOURCE": "aws", "SECRET_ID": "s"}, client)


@pytest.mark.parametrize(
    ("body", "message"), [("not json", "not valid JSON"), ("[1]", "JSON object")]
)
def test_rejects_secrets_that_are_not_a_json_object(body: str, message: str) -> None:
    with pytest.raises(SecretsError, match=message):
        load_secrets({"SECRETS_SOURCE": "aws", "SECRET_ID": "s"}, client_returning(body))


def test_local_mode_never_calls_aws_and_does_not_override_real_env_vars() -> None:
    client = client_returning("{}")
    env = {"SECRETS_SOURCE": "local", "DATABASE_URL": "from-real-env"}
    load_secrets(env, client)
    client.get_secret_value.assert_not_called()
    assert env["DATABASE_URL"] == "from-real-env"


def test_rejects_an_unknown_source() -> None:
    with pytest.raises(SecretsError, match='got "vault"'):
        load_secrets({"SECRETS_SOURCE": "vault"})
