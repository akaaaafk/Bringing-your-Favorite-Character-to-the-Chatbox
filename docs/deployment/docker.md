# Portable Docker deployment

The project uses Modal plus Vercel for its hosted demo.
`deploy/docker/Dockerfile` is the portable alternative: it builds the React
client and serves it from the same FastAPI container as the model endpoints.

## Required local artifacts

Before building, place these files at their documented paths:

```text
config/personas.json
models/classifier/model.safetensors
models/generator/adapter_model.safetensors
```

Run the preflight and build from the repository root:

```bash
python tools/preflight.py --target docker
docker build -f deploy/docker/Dockerfile -t movie-persona-api .
docker run --rm -p 8000:8000 movie-persona-api
```

Open `http://localhost:8000` for the UI or
`http://localhost:8000/docs` for the API documentation.

For a CUDA image, pass a compatible PyTorch wheel index:

```bash
docker build \
  -f deploy/docker/Dockerfile \
  --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu130 \
  -t movie-persona-api:cuda .
```

The host must provide the NVIDIA Container Toolkit when running a CUDA image.
