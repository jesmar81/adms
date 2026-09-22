FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app \
    && chown -R app:app /srv/app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
