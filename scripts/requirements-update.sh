#!/usr/bin/env bash
set -eu

# List of package names
packages=("aiodns" "aiofiles" "aiohttp-jinja2" "aiohttp" "cachetools" "coloredlogs" "cryptography" "defusedxml" "gmqtt" "Jinja2" "passlib" "setuptools" "tinydb" "websockets" "validators")

echo "" >requirements.txt
# Loop through the packages
for package in "${packages[@]}"; do
  # Get the latest version number using jq and curl
  latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" | jq -r '.releases | keys | .[]' | sort -V | tail -n 1)
  # Print the formatted output
  echo "${package}==${latest_version}" >>requirements.txt
done

# ------------------------------------------------------------------------------

packages_dev=("mypy" "pre-commit" "pycountry" "pylint" "pytest-aiofiles" "pytest-aiohttp" "pytest-asyncio" "pytest-cov" "pytest-docker-fixtures" "pytest-env" "pytest-timeout" "pytest" "ruff" "testfixtures" "types-aiofiles" "types-cachetools" "types-mock" "types-pillow" "types-pytz")

echo "" >requirements-dev.txt
# Loop through the packages
for package in "${packages_dev[@]}"; do
  # Get the latest version number using jq and curl
  latest_version=$(curl -s "https://pypi.org/pypi/${package}/json" | jq -r '.releases | keys | .[]' | sort -V | tail -n 1)
  # Print the formatted output
  echo "${package}>=${latest_version}" >>requirements-dev.txt
done
