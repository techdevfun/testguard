#!/bin/sh
# Example CI gate: fail the build when tests look manipulated.
# Usage: sh examples/ci/check.sh
set -eu
cd "$(dirname "$0")/../.."

python3 -m unittest discover -s tests
python3 -m testguard tests/fixtures/py_clean.py \
  tests/fixtures/js_clean.test.js examples/clean-demo
