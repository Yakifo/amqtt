# Release Procedure

This checklist is for maintainers publishing a new aMQTT release. PyPI package
builds, GitHub artifact attestations, and PyPI Trusted Publishing are automated
through GitHub Actions.

## Prerequisites

- GitHub permissions to create release branches, merge release PRs, push release
  tags, and publish GitHub releases.
- A GitHub environment named `pypi`, with required reviewers enabled.
- A PyPI Trusted Publisher configured for:
  - Owner: `Yakifo`
  - Repository: `amqtt`
  - Workflow: `publish-pypi.yml`
  - Environment: `pypi`
- Docker Hub and ReadTheDocs permissions for downstream publishing.

Do not configure a long-lived PyPI token in GitHub secrets for the automated
release workflow. PyPI receives a short-lived token through Trusted Publishing.

## Step 1. Create a Release Branch

```shell
git switch main
git pull --ff-only
git switch -c release/0.12.0
```

## Step 2. Update Version References

Update every version reference for the release:

- `pyproject.toml`
- `amqtt/__init__.py`
- `Makefile`
- `uv.lock`
- `docs/changelog.md`

The release notes in `docs/changelog.md` are copied into the draft GitHub
release by `.github/workflows/release-drafter.yml`.

## Step 3. Run Checks

```shell
uv sync --locked --dev --all-extras
uv run --frozen pytest tests/
uv run --frozen mypy amqtt/
uv run --frozen pylint amqtt/
uv run --frozen ruff check amqtt/
```

Optionally run the same constrained package build used by the PyPI workflow:

```shell
uv build --build-constraints .github/build-constraints.txt --sdist --wheel --out-dir dist
```

## Step 4. Open and Merge a Release PR

Open a release PR on GitHub. Merge it into `main` after CI passes and the PR is
approved.

## Step 5. Push the Release Tag

Release tags must use a valid PyPI-compatible `v` version, such as `v0.12.0` or
`v0.12.0-rc.1`.

```shell
git switch main
git pull --ff-only
git tag -a v0.12.0 -m "aMQTT 0.12.0"
git push origin v0.12.0
```

Pushing the tag runs `.github/workflows/release-drafter.yml`, which validates the
tag and creates or updates a draft GitHub release using `docs/changelog.md` as
the release body.

## Step 6. Publish the GitHub Release

Review the draft release on GitHub. Confirm the release title, tag, and notes,
then publish it.

Publishing the GitHub release triggers `.github/workflows/publish-pypi.yml`.
That workflow:

- validates the release tag format
- builds the sdist and wheel with `.github/build-constraints.txt`
- verifies that built package metadata matches the release tag
- uploads the distributions as a workflow artifact
- generates GitHub artifact attestations for the distributions
- publishes the distributions to PyPI through Trusted Publishing
- uploads PyPI publish attestations automatically

## Step 7. Verify PyPI

After the PyPI workflow completes, verify the published release:

```shell
uv run --with amqtt==0.12.0 --no-project amqtt --help
```

Also confirm that the release is visible at:

```text
https://pypi.org/project/amqtt/0.12.0/
```

## Step 8. Publish Downstream Resources

Publish Docker images:

```shell
make init
make build
```

This publishes:

- `amqtt/amqtt:latest`
- `amqtt/amqtt:<version>`

Finally, log into ReadTheDocs and add the new version if it is not enabled
automatically.
