# Contributing to synaptic-graph

Thanks for your interest in contributing!

## Getting started

1. Fork the repository and clone it locally:

```bash
git clone https://github.com/your-username/synaptic
cd synaptic
```

2. Create a virtual environment and install in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. Create a branch for your change:

```bash
git checkout -b feat/my-feature
```

## Making changes

- Keep changes focused — one feature or fix per PR.
- Follow the existing code style (no formatter enforced, just be consistent).
- If you add a new detection category (e.g. a new cloud SDK), add it in the appropriate detector file.

## Submitting a PR

1. Make sure the CLI works end-to-end: `synaptic scan ./synaptic`
2. Push your branch and open a pull request against `main`.
3. Describe what the change does and why.

## Reporting issues

Open an issue at [github.com/Darkvus/synaptic/issues](https://github.com/Darkvus/synaptic/issues) with:
- What you ran
- What you expected
- What actually happened (paste the full error if any)

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
