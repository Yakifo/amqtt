import subprocess


def test_smometest():
    output = subprocess.check_output(["amqtt", "--help"])
    assert b"Usage" in output
    assert b"aMQTT" in output

    output = subprocess.check_output(["amqtt_sub", "--help"])
    assert b"Usage" in output
    assert b"amqtt_sub" in output

    output = subprocess.check_output(["amqtt_pub", "--help"])
    assert b"Usage" in output
    assert b"amqtt_pub" in output
