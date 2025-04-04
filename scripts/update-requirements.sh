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

packages_dev=(mypy pre-commit pycountry pylint pytest-aiofiles pytest-aiohttp pytest-asyncio pytest-cov pytest-docker-fixtures pytest-env pytest-timeout pytest ruff testfixtures types-aiofiles types-cachetools types-mock types-pillow types-pytz types-PyYAML hypothesis pytest-logdog psutil setuptools types-setuptools)

echo "" >requirements-dev.txt
# Loop through the packages
for package in "${packages_dev[@]}"; do
  # Get the latest version number using jq and curl
  latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" | jq -r '.releases | keys | .[]' | sort -V | tail -n 1)
  # Print the formatted output
  echo "\"${package}>=${latest_version}\",  # https://pypi.org/project/${package}" >>requirements-dev.txt
done
