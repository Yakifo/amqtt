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
