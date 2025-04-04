# Contributing to aMQTT

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

The following is a set of guidelines for contributing to aMQTT on GitHub. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Development Setup

### Requirements

1. python installed (at least one version, for developers it might be helpful to have multiple versions, e.g. 3.13 installed for testing purposes)
2. [uv](https://docs.astral.sh/uv/guides/install-python/) installed

### Testing the newest development version

Create virtual environment with `UV`

```sh
uv venv --python 3.13.0
```

Install:

```sh
uv sync --no-dev
```

Usage:

```sh
uv run amqtt
uv run amqtt_pub
uv run amqtt_sub
```

### Setup development tools

Install with:

```sh
uv sync
```

This will install all dependencies needed for development.

Afterwards you can use `pytest` etc.

## Testing

When adding a new feature please add a test along with the feature. The testing coverage should not decrease.
If you encounter a bug when using aMQTT which you then resolve, please reproduce the issue in a test as well.

## Style and linting

We use `ruff` at default settings. To avoid repeated pushes to satisfy our CI linter, you can use [pre-commit](https://pre-commit.com). Install the necessary hooks with `pre-commit install`.
