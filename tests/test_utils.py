import yaml
from hypothesis import given, strategies as st
from hypothesis import provisional

from amqtt.session import Session
from amqtt import utils


@given(st.text())
def test_format_client_message(client_id):
    test_session = Session()
    test_session.client_id = client_id
    client_message = utils.format_client_message(session=test_session)

    assert client_message == f"(client id={client_id})"


@given(provisional.urls(), st.integers())
def test_format_client_message_valid(url, port):
    client_message = utils.format_client_message(address=url, port=port)
    assert client_message == f"(client @={url}:{port})"


def test_format_client_message_unknown():
    client_message = utils.format_client_message()
    assert client_message == "(unknown client)"


def test_client_id():
    client_id = utils.gen_client_id()
    assert isinstance(client_id, str)
    assert client_id.startswith("amqtt/")


def test_read_yaml_config(tmpdir):
    fn = tmpdir / "test.config"
    with open(fn, "w") as f:
        yaml.dump({"a": "b"}, f)

    configuration = utils.read_yaml_config(config_file=fn)
    assert configuration == {"a": "b"}
