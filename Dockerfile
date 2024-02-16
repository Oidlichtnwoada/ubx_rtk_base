FROM python:3.12.2-slim-bookworm as builder

RUN pip install poetry==1.7.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --no-root

FROM python:3.12.2-slim-bookworm as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    TZ="UTC"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN apt update && apt install rtklib

COPY ubx_rtk_base ./ubx_rtk_base

ENTRYPOINT ["python", "-m", "ubx_rtk_base.main"]
