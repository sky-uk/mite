# Migration to Hatch

It was time to move away from setuptools and tox to hatch.


## What changed
All the configuration that was spread throughout the multiple files (requirements.txt, setup.py, setup.cfg, tox.ini, dev-requirements.txt, test-requirements.txt) has been consolidated inside the pyproject.toml file that hatch uses to set up environments, run lint jobs, and run tests.

As a consequence of this migration, we moved from multiple different linters/checkers to ruff, which can be fully configured in pyproject.toml. Ruff replaces black, flake8, isort, and other tools with a single, faster linter and formatter.

The pre-commit hook is now also updated to use hatch. There are currently 145 errors 🥲 which are not going to be fixed as part of this PR as it will just create chaos.

### How to set up Hatch

First, install hatch and initialize the mite project following its documentation:
- Installation: https://hatch.pypa.io/latest/install/
- Existing project init: https://hatch.pypa.io/latest/intro/#existing-project

### Envs
There are currently 3 environments configured in hatch (more info: https://hatch.pypa.io/latest/environment/):
- **default**: Designed for general development withall optional features and dev dependencies
- **lint**: Designed for running ruff (linting and formatting)
- **test**: To run the test suite across multiple Python versions (3.10, 3.11)

Apart from the default environment which is used while developing new mite code, fixes, and bug fixes, the other environments can be invoked as needed for running tests and checks.


#### Run unit tests
Below are the different ways to run tests:

Run tests across all Python versions:
```bash
hatch run test:test
```

Run tests with coverage, creating an HTML report:
```bash
hatch run test:test-cov
```

Run tests on a specific Python version:
```bash
hatch run test.py3.10:test
hatch run test.py3.11:test
```

Run specific test markers (for example, skip tests marked as slow):
```bash
hatch run test:test -m "not slow"
```

Open the coverage HTML report:
```bash
hatch run test:cov-report
```

#### Run ruff
Use the lint environment to run the check command:
```bash
hatch run lint:check
```

This runs both `ruff check` (linting) and `ruff format --check` (format checking).

Use `format` to run checks and automatically fix what ruff can fix:
```bash
hatch run lint:format
```

This runs `ruff check --fix` and `ruff format` to auto-fix issues and format code.