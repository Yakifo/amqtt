# Release Procedure

This checklist is for maintainers publishing a new aMQTT release. It has not yet been automated.

## Prerequisites

- Publishing credentials are needed for:
  - Github releases, tags and PRs
  - PyPI
  - ReadTheDocs
  - Docker Hub
- Trusted publisher identity for PyPI attestations: github (preferred), google or microsoft account

### Step 1. Create a release branch

```shell
   git checkout -c release/0.11.4
```

### Step 2. Update version references

   - `pyproject.toml`
   - `amqtt/__init__.py`
   - `Makefile`



   - `docs/changelog.md`

### Step 3. Run checks

   ```shell
   uv sync --locked --dev --all-extras
   uv run --frozen pytest tests/
   uv run --frozen mypy amqtt/
   uv run --frozen pylint amqtt/
   uv run --frozen ruff check amqtt/
   ```

### Step 4. Open a release PR on GitHub

### Step 5. Merge the release PR into `main`

Once CI passes and the PR is approved 

### Step 6. Push the tag to GitHub

```shell
git switch main
git pull
git tag -a v0.11.4 -m "aMQTT 0.11.4"
git push origin v0.11.4
```

## Publishing a signed python package

### Step 7. Build the Package Artifacts

Use uv to execute hatch build within a clean, isolated environment. This generates source distribution (.tar.gz) and wheel (.whl) files: 

```shell
uv run hatch build
```

### Step 8. Generate PyPI/Sigstore Attestations

Generate cryptographic signature bundles. This triggers an interactive OAuth 2.0 flow via your web browser to securely bind your identity (GitHub, Google, or Microsoft account) to the cryptographic signature and records the event in a public transparency log:

```shell

uv run --with pypi-attestations python -m pypi_attestations sign dist/amqtt-0.11.4.tar.gz
uv run --with pypi-attestations python -m pypi_attestations sign dist/amqtt-0.11.4-py3-none-any.whl
```

This command outputs two signature bundle files inside your folder:

* `dist/amqtt-0.11.4.tar.gz.publish.attestation`
* `dist/amqtt-0.11.4-py3-none-any.whl.publish.attestation`

### Step 9. Verify the Attestations Locally

Validate the cryptographic bundles locally before uploading them to the registry. Use the `<signing-identity>` with the exact email address used during previous step.

```shell

uv run --with pypi-attestations python -m pypi_attestations verify attestation \
  --identity <signing-identity> \
  dist/amqtt-0.11.4.tar.gz

uv run --with pypi-attestations python -m pypi_attestations verify attestation \
  --identity <signing-identity> \
  dist/amqtt-0.11.4-py3-none-any.whl
```

### Step 10.  Publish to Test PyPI using `hatch`

```shell
uv run hatch publish -r testpypi
```

In a new, clean directory, install from TestPyPI, along with a quick test:

```shell
uv venv
uv run python3 -m pip install --index-url https://test.pypi.org/simple/ amqtt
uv run amqtt
```

### Step 11. Publish to PyPI

```shell
uv run hatch publish
```

**Note: PyPI requires an automatic CI/CD based pipeline to publish attestations.**

## Publish to downstream resources

### Step 12: GitHub Release

Create a GitHub release, include the `docs/changelog.md` file as release notes. Upload the following files from the `dist/` directory as release assets:

* The source distribution (.tar.gz)
* The wheel (.whl)
* Both digital attestation files (*.publish.attestation)

### Step 13: Publish Docker Image

Initialize the Docker builder if needed:

```shell
make init
```

Build and push multi-platform images:

```shell
make build
```

This publishes:

- `amqtt/amqtt:latest`
- `amqtt/amqtt:<version>`

### Step 14: Add release to ReadTheDocs builds

Log into ReadTheDocs and add the new version; the docs will be built automatically.
