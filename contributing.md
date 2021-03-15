# Contributing to AMQTT

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

The following is a set of guidelines for contributing to AMQTT on GitHub. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Testing

When adding a new feature please add a test along with the feature. The testing coverage should not decrease.
If you encounter a bug when using AMQTT which you then resolve, please reproduce the issue in a test as well.

## Style and linting

We use `black` at default settings along with `flake8`. To avoid repeated pushes to satisfy our CI linter, you can use [pre-commit](https://pre-commit.com). Install the necessary hooks with `pre-commit install`.