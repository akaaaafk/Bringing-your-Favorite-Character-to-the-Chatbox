# Interface Contracts Between Phases

Production and evaluation code import from the package classifier interface:

    from movie_persona.classifier import predict_persona, predict_persona_batch

`predict_persona(text: str) -> dict[str, float]` returns a probability
distribution over the 5 selected characters' persona_tags, e.g.
`{"jack": 0.71, "bateman": 0.12, "alvy": 0.09, "ben": 0.05, "erin": 0.03}`.

This auto-detects a trained model at `models/classifier/`.
Until that checkpoint exists, it returns correctly-shaped stub
predictions so downstream code can be built and tested early.

Character list and persona tags live in the checked-in `config/personas.json`
manifest. Training, inference, and deployment all read this same file.
Labels: `alvy`, `bateman`, `ben`, `erin`, `jack`.
