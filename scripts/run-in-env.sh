#!/usr/bin/env bash
set -eu

# Enable debug mode if DEBUG=true is set in the environment
DEBUG=${DEBUG:-false}
if [ "$DEBUG" = "true" ]; then
  set -x
fi

# Resolve project root directory
my_path=$(git rev-parse --show-toplevel)

# Activate pyenv virtualenv if .python-version exists
if [ -s "${my_path}/.python-version" ]; then
  PYENV_VERSION=$(head -n 1 "${my_path}/.python-version")
  if command -v pyenv >/dev/null 2>&1; then
    export PYENV_VERSION
    echo "Activating pyenv version: ${PYENV_VERSION}" >&2
  else
    echo "Warning: pyenv not found, skipping pyenv activation." >&2
  fi
fi

# Check for and activate common virtual environments
venvs=("venv" ".venv")
for venv in "${venvs[@]}"; do
  activate_script="${my_path}/${venv}/bin/activate"
  if [ -f "$activate_script" ]; then
    echo "Activating virtual environment: ${venv}" >&2
    # Deactivate any existing venv and activate the new one
    deactivate 2>/dev/null || true
    # shellcheck source=/dev/null
    . "$activate_script"
    break
  fi
done

# Check if we are in a virtual environment
if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "Warning: No virtual environment found. Running in global Python environment." >&2
fi

# Execute the specified command
exec "$@"
