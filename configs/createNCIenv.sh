#!/bin/bash

ENV_PATH=$1
SCRIPT_PATH=$(basename "$0")
REPO_ROOT=$(dirname $(dirname "$0"))

if [[ -z "$ENV_PATH" ]]; then
  echo "Usage: $SCRIPT_PATH <path_to_new_env_dir>"
  exit 1
fi

if [[ -e "$ENV_PATH" ]]; then
  echo "Error: env path already exists!"
  exit 1
fi

# Activate NCI base env
pushd $REPO_ROOT > /dev/null
source configs/activateNCI.env

# Create new venv
python3 -m venv $ENV_PATH
source $ENV_PATH/bin/activate

# Add stand-alone env script for gamma_insar
sed -e 's|VENV_PATH=$1'"|VENV_PATH=$ENV_PATH|" $REPO_ROOT/configs/activateNCI.env > $ENV_PATH/NCI.env

# Upgrade pip (very important, wrong package version resolution with older PIP versions)
python -m pip install --upgrade pip

# Install dependencies and gamma_insar into venv
python3 -m pip install -r requirements.txt
python setup.py install

echo "Environment successfully created!"
popd > /dev/null
