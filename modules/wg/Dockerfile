FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 wg \
    && mkdir -p /data \
    && chown wg:wg /data \
    && chown -R wg:wg /app
USER wg

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3000

# --forwarded-allow-ips="*" is safe here: the container has no published
# port (see compose.yaml), so the only traffic it ever sees on PORT comes
# from the toolsite Caddy inside the private toolsite_net network.
CMD uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000} --workers 1 --proxy-headers --forwarded-allow-ips="*"
