# Contributing to aMQTT

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

The following is a set of guidelines for contributing to aMQTT on GitHub. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Development Setup


### Requirements

1. python installed (at least one version, for developers it might be helpful to have multiple versions, e.g. 3.7 and 3.9 installed for testing purposes)
2. [poetry](https://python-poetry.org/docs/#installation) installed


### Testing the newest development version

Poetry will create a virtual environment for you

Install:
```
poetry install --no-dev
```

Usage:
```
poetry run amqtt
poetry run amqtt_pub
poetry run amqtt_sub
```

Or you can enter the virtual enviroment via:
```
poetry shell
```

And then run the commands without prefixing them with `poetry run`

### Setup development tools

Install with:
```
poetry install
```
This will install all dependencies needed for development.
A virtual environment will be created and can be entered with `poetry shell`.

Afterwards you can use `pytest` etc.

If you have multiple python installations you can choose which one to use with poetry with `poetry env`, this is helpful for switching between python versions for testing.


## Testing

When adding a new feature please add a test along with the feature. The testing coverage should not decrease.
If you encounter a bug when using aMQTT which you then resolve, please reproduce the issue in a test as well.

## Style and linting

We use `black` at default settings along with `flake8`. To avoid repeated pushes to satisfy our CI linter, you can use [pre-commit](https://pre-commit.com). Install the necessary hooks with `pre-commit install`.
