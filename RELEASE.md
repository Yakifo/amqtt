# Release Procedure

This checklist is for maintainers publishing a new aMQTT release. It has not yet been automated.

## Prerequisites

- Publishing credentials are needed for PyPI, ReadTheDocs and Docker Hub

## Prepare the Release

1. Create a release branch:

```shell
   git checkout -c release/0.11.4
```

2. Update version references:

   - `pyproject.toml`
   - `amqtt/__init__.py`
   - `Makefile`
   - `docs/changelog.md`

3. Run checks:

   ```shell
   uv sync --locked --dev --all-extras
   uv run --frozen pytest tests/
   uv run --frozen mypy amqtt/
   uv run --frozen pylint amqtt/
   uv run --frozen ruff check amqtt/
   ```

4. Open a release PR on GitHub.

## Tag the Release

After the release PR is merged:

```shell
git switch main
git pull
git tag v0.11.4
git push origin v0.11.4
```

## Build and Publish Python Package

Build the package:

```shell
uv run hatch build
```

Publish to TestPyPI first:

```shell
uv run hatch publish -r testpypi
```

Install from TestPyPI:

```
python3 -m pip install --index-url https://test.pypi.org/simple/ amqtt
```

Smoke test with:

```shell
uv run amqtt
```


Publish to PyPI:

```shell
uv run hatch publish
```

## Publish Docker Image

Initialize the Docker builder if needed:

```shell
make init
```

Build multi-platform images:

```shell
make build-local
```

Build and push multi-platform images:

```shell
make build
```

This publishes:

- `amqtt/amqtt:latest`
- `amqtt/amqtt:<version>`

## Post-Release Checks

- Log into ReadTheDocs and add the new version; the docs will be built automatically.
- Publish a new release on GitHub.
