# QuackQuant Mac Studio deployment

This repo is set up for a hybrid deployment:

- Docker Compose runs the static website, FastAPI backend, Postgres, Redis, and Caddy reverse proxy.
- Local model serving runs natively on the Mac Studio and exposes an OpenAI-compatible HTTP endpoint.

That split keeps the app reproducible while leaving model inference free to use the best Apple
Silicon runtime available for your hardware.

## 1. Install prerequisites on the Mac Studio

Install one container runtime:

- Docker Desktop, or
- OrbStack

Then clone or copy this repository onto the Mac Studio.

## 2. Create deploy environment

From the repository root:

```bash
cp deploy/.env.example .env
```

Edit `.env` and change at least:

```bash
POSTGRES_PASSWORD=change_me_to_a_long_random_value
MAC_STUDIO_HOSTNAME=macstudio.local
```

Use the Mac Studio's LAN hostname or IP address for `MAC_STUDIO_HOSTNAME` if you want to open the
site from another device.

## 3. Start the app stack

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:8080
```

Health check:

```bash
curl http://localhost:8080/api/v1/health
```

Useful operations:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f web
docker compose down
```

## 4. Native model server

Keep the model server outside this Compose stack at first. Have it listen on the Mac Studio host,
for example:

```text
http://127.0.0.1:8002
```

The backend container can reach the Mac host through:

```text
http://host.docker.internal:8002
```

That value is already wired as:

```bash
QUACKQUANT_MODEL_SERVER_BASE_URL=http://host.docker.internal:8002
```

If you serve with vLLM, MLX, llama.cpp, Ollama, or another runtime, prefer an OpenAI-compatible API
surface so QuackQuant can swap providers without rewriting agent code.

## 5. Recommended production hardening

Before exposing this beyond your private LAN:

- add HTTPS and a real hostname in `deploy/Caddyfile`;
- store broker/API secrets in `.env` only, never in git;
- add database migrations before creating persistent app tables;
- add authentication before broker, strategy, or agent endpoints become active;
- keep live trading disabled until the paper-trading risk gates are implemented;
- add Mac launch/startup automation only after manual `docker compose up` is reliable.

## 6. Why not venv-only?

A venv is great for development, but deployment becomes fragile because the Mac Studio must have the
same Python, system packages, environment variables, process commands, database, Redis, and reverse
proxy setup. Compose packages those moving parts into a repeatable stack.

Use venv for coding. Use Compose for the always-on app.
