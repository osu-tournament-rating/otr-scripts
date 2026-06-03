# otr-scripts

## Getting started

Install deps:

```
uv venv --python 3.14
uv pip install .
```

## End-to-end tests

External e2e tests live under `tests/e2e`. The public replica import scenario
downloads the latest public archive and hash from GCS, verifies the SHA256
line, and restores the dump into an isolated `postgres:17` Docker container.

```
uv pip install '.[e2e]'
python -m pytest -m e2e tests/e2e
```
