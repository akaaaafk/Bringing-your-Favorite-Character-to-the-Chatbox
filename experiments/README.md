# Experiments

This directory contains reproducibility code, not production runtime code.

- `scripts/` provides the data preparation, classifier training, generator
  training, and Best-of-N evaluation entrypoints.
- `notebooks/` preserves the exploratory workflows used during development.

Run scripts and notebooks with `final_project/` as the working directory so
their stable `config/`, `data/`, `models/`, and `results/` paths resolve
correctly. Install experiment dependencies with:

```bash
python -m pip install -e ".[training]"
```

See the root `README.md` for the recommended execution order.
