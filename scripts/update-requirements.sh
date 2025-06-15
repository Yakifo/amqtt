#!/usr/bin/env bash
set -eu

# List of package names
packages=(transitions websockets passlib docopt PyYAML)

echo "" >requirements.txt
# Loop through the packages
for package in "${packages[@]}"; do
  # Get the latest version number using jq and curl
  latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" | jq -r '.releases | keys | .[]' | sort -V | tail -n 1)
  # Print the formatted output
  echo "\"${package}==${latest_version}\",  # https://pypi.org/project/${package}" >>requirements.txt
done

# ------------------------------------------------------------------------------

packages_dev=(hypothesis mypy pre-commit psutil pylint pytest-asyncio pytest-cov pytest-logdog pytest-timeout pytest ruff setuptools types-mock types-PyYAML types-setuptools)

echo "" >requirements-dev.txt
# Loop through the packages
for package in "${packages_dev[@]}"; do
  # Get the latest version number using jq and curl
  latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" | jq -r '.releases | keys | .[]' | sort -V | tail -n 1)
  # Print the formatted output
  echo "\"${package}>=${latest_version}\",  # https://pypi.org/project/${package}" >>requirements-dev.txt
done
