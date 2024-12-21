import subprocess


def test_smometest():
    amqtt_path = "amqtt"
    output = subprocess.check_output([amqtt_path, "--help"])  # noqa: S603
    assert b"Usage" in output
    assert b"aMQTT" in output

    amqtt_sub_path = "amqtt_sub"
    output = subprocess.check_output([amqtt_sub_path, "--help"])  # noqa: S603
    assert b"Usage" in output
    assert b"amqtt_sub" in output

    amqtt_pub_path = "amqtt_pub"
    output = subprocess.check_output([amqtt_pub_path, "--help"])  # noqa: S603
    assert b"Usage" in output
    assert b"amqtt_pub" in output
