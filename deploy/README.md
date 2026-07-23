# QuackQuant Mac Studio deployment

This repo is set up for a lightweight local deployment:

- Docker Compose runs the static dashboard, FastAPI backend, and Caddy reverse proxy.
- Optional local model serving, such as Ollama, runs natively on the Mac Studio.

That split keeps the app reproducible while leaving model inference free to use the best local
runtime available for your hardware.

## 1. Install prerequisites on the Mac Studio

Install one container runtime:

- Docker Desktop, or
- OrbStack

Then clone or copy this repository onto the Mac Studio.

## 2. Optional deploy environment

Create `.env` only if you want to override the default HTTP port or hostname:

```bash
QUACKQUANT_HTTP_PORT=8080
MAC_STUDIO_HOSTNAME=macstudio.local
```

Use the Mac Studio's LAN hostname or IP address for `MAC_STUDIO_HOSTNAME` when opening the site from
another device.

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

## 4. Optional Native Model Server

Keep Ollama or another model server outside this Compose stack at first. Have it listen on the Mac
Studio host, for example:

```text
http://127.0.0.1:11434
```

The backend container can reach the Mac host through:

```text
http://host.docker.internal:8002
```

That value is already wired as:

```bash
QUACKQUANT_OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Scanner math does not require an LLM. Use the model server later for explanations, journal reviews,
and strategy comparison.

## 5. Recommended production hardening

Before exposing this beyond your private LAN:

- add HTTPS and a real hostname in `deploy/Caddyfile`;
- store broker/API secrets in `.env` only, never in git;
- add authentication before broker or agent execution endpoints become active;
- keep live trading disabled until the paper-trading risk gates are implemented;
- add Mac launch/startup automation only after manual `docker compose up` is reliable.

## 6. Why not venv-only?

A venv is great for development, but deployment becomes fragile because the Mac Studio must have the
same Python, system packages, environment variables, process commands, and reverse proxy setup.
Compose packages those moving parts into a repeatable stack.

Use venv for coding. Use Compose for the always-on app.
