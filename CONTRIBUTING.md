# Contributing to aMQTT

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

The following is a set of guidelines for contributing to aMQTT on GitHub. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Development Setup

### Requirements

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Use `uv python install <version>` to install [3.10, 3.11, 3.12 or 3.13](https://docs.astral.sh/uv/guides/install-python/)
3. Fork repository (if you intend to open a pull request)
4. Clone repo `git clone git@github.com:<username>/amqtt.git`
5. Add repo to receive latest updates `git add upstream git@github.com:Yakio/amqtt.git`

### Installation

Create and start virtual environment with `UV`

```shell
uv venv .venv --python 3.13.0
source .venv/bin/activate
```

Install the package with development (and doc) dependencies:

```shell
uv pip install -e . --group dev --group doc
```

Add git pre-commit checks (which parallel the CI checks):

```shell
pre-commit install
```

### Run

Run CLI commands:

```shell
uv run amqtt
uv run amqtt_pub
uv run amqtt_sub
```

Run the test case suite:

```shell
pytest
```

Run the type checker and linters manually:

```shell
pre-commit run --all-files
```

## Testing

When adding a new feature, please add corollary tests. The testing coverage should not decrease.
If you encounter a bug when using aMQTT which you then resolve, please reproduce the issue in a test as well.

## Go MQTT Interoperability Tests

Some interoperability tests use the Eclipse Paho Go MQTT client. To run them locally, install Go with `go` on your `PATH`, then download the Go module dependencies:

```shell
cd tests/support/go-mqtt-client
go mod download
cd -
```

Then run the Go interoperability tests:

```shell
uv run pytest tests/test_go_mqtt.py -v
```

If Go or the downloaded module dependencies are unavailable, these tests are skipped during local runs. In CI, missing Go dependencies are treated as failures.

## Java MQTT Interoperability Tests

Some interoperability tests use the Eclipse Paho Java MQTT client. To run them locally, install a JDK with `java` and `javac` on your `PATH`, then download the Paho client jar and expose it with `PAHO_MQTT_JAR`:

```shell
curl -L -o /tmp/org.eclipse.paho.client.mqttv3-1.2.5.jar \
  https://repo1.maven.org/maven2/org/eclipse/paho/org.eclipse.paho.client.mqttv3/1.2.5/org.eclipse.paho.client.mqttv3-1.2.5.jar
export PAHO_MQTT_JAR=/tmp/org.eclipse.paho.client.mqttv3-1.2.5.jar
```

Then run the Java interoperability tests:

```shell
uv run pytest tests/test_java_mqtt.py -v
```

If `PAHO_MQTT_JAR` is unset, pytest also checks the local Maven and Gradle caches for `org.eclipse.paho.client.mqttv3`. If no jar is available, these tests are skipped.
