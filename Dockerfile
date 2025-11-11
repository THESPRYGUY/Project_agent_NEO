FROM python:3.11-slim

ARG GIT_SHA=UNKNOWN
ENV GIT_SHA=${GIT_SHA}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app \
    HOST=0.0.0.0 \
    PORT=5000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user and group
RUN groupadd -g 10001 appgroup \
 && useradd -r -u 10001 -g appgroup appuser
# Copy only what we need to install and run
COPY pyproject.toml README.md ./
COPY src ./src
COPY neo_build ./neo_build
COPY wsgi.py ./

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir gunicorn \
 && pip install --no-cache-dir -e .

# Ensure permissions for non-root execution
RUN chown -R appuser:appgroup /app
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:5000/health || exit 1

USER appuser

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "wsgi:app"]
