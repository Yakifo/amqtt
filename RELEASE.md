# Release Procedure

This checklist is for maintainers publishing a new aMQTT release. PyPI package
builds, GitHub artifact attestations, and PyPI Trusted Publishing are automated
through GitHub Actions.

## Prerequisites

- GitHub permissions to create release branches, merge release PRs, push release
  tags, and publish GitHub releases.
- A GitHub environment named `pypi`, with required reviewers enabled.
- A GitHub environment named `testpypi`, used only for rehearsal runs.
- A PyPI Trusted Publisher configured for:
  - Owner: `Yakifo`
  - Repository: `amqtt`
  - Workflow: `publish-pypi.yml`
  - Environment: `pypi`
- A **separate** TestPyPI Trusted Publisher, registered at
  <https://test.pypi.org/manage/account/publishing/>, with the same owner,
  repository, and workflow but environment `testpypi`. The PyPI publisher does
  not cover test.pypi.org. Only the rehearsal path needs this; normal releases
  do not.
- Docker Hub and ReadTheDocs permissions for downstream publishing.

Do not configure a long-lived PyPI token in GitHub secrets for the automated
release workflow. Both indexes receive a short-lived token through Trusted
Publishing.

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

`pyproject.toml` and `amqtt/__init__.py` must match exactly. CI enforces this in
the `code-quality` job, because the publish workflow only compares the release
tag against built package metadata — it cannot catch a stale `__version__`, which
is what `amqtt --version` and the `$SYS` topic report.

Versions use the PEP 440 form, including release candidates: `0.12.0`,
`0.12.0rc1`. The release tag is the same string with a `v` prefix, so there is
only ever one spelling to keep straight.

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

Release tags must take exactly one of two forms. The tag alone determines which
index the distributions are published to:

| Tag form | Example | Publishes to |
| --- | --- | --- |
| `vMAJOR.MINOR.PATCH` | `v0.12.0` | PyPI |
| `vMAJOR.MINOR.PATCHrcN` | `v0.12.0rc1` | PyPI, as a pre-release |

Tags are the PEP 440 version with a `v` prefix, so stripping the `v` yields
exactly the version in `pyproject.toml`, `amqtt/__init__.py`, and on the index.
No other form is accepted — not `v0.12`, not the older dotted `v0.12.0-rc.1`
used before 0.12.0, and not `alpha`, `beta`, `dev`, or `post` variants. The same
pattern is enforced in `ci.yml`, `release-drafter.yml`, and `publish-pypi.yml`,
so a malformed tag fails at push time rather than after publishing.

Release candidates go to production PyPI. This is safe by construction: PEP 440
resolvers exclude pre-releases unless asked, so `pip install amqtt` continues to
resolve to the latest stable version, and testers opt in explicitly with
`--pre` or an exact pin. It also means release candidates are tested against the
same dependency resolution real users get.

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

For a release candidate, verify the pin resolves and stop here — steps 7 and 8
apply to full releases only:

```shell
uv run --with amqtt==0.12.0rc1 --no-project amqtt --help
```

Confirm it appears at <https://pypi.org/project/amqtt/0.12.0rc1/>, and that
`uv run --with amqtt --no-project amqtt --version` still reports the previous
stable version — pre-releases must not be picked up without `--pre`.

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

## Appendix. Rehearsing a Publish to TestPyPI

TestPyPI is not part of the release path. It exists to exercise the publishing
machinery — Trusted Publishing, attestations, metadata validation — without
touching PyPI, which is useful after changing `publish-pypi.yml` itself.

The tag must already be **pushed to GitHub** — the runner clones from the remote,
so a tag that exists only locally cannot be checked out. Pushing a tag is safe
on its own: it triggers `release-drafter.yml`, which creates a *draft* release,
and a draft does not emit the `release: published` event that `publish-pypi.yml`
listens for. Nothing reaches an index until you publish the release.

That makes the rehearsal an optional step wedged into step 5:

```shell
# 1. Push the tag. Creates a draft release; publishes nothing.
git push origin v0.12.0rc1

# 2. Rehearse to TestPyPI.
gh workflow run publish-pypi.yml -f tag=v0.12.0rc1

# 3. If it succeeds, publish the draft release (step 6) to reach PyPI.
```

`skip-existing` is enabled for TestPyPI, so repeat rehearsals of the same version
are not an error.

Two notes on `workflow_dispatch`: the "Run workflow" button only appears once a
workflow carrying that trigger is on the **default branch**, and the dispatch
runs the workflow *definition* from the ref you select while building the code
from the `tag` input. That separation is deliberate — it lets you rehearse a
changed `publish-pypi.yml` against an older tag.

Installing from TestPyPI resolves dependencies against a different index than
production, so it validates the upload, not the package:

```shell
uv run --with amqtt==0.12.0rc1 --no-project \
  --index https://test.pypi.org/simple/ --index-strategy unsafe-best-match \
  amqtt --help
```
