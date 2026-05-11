# ── Backend Dockerfile ────────────────────────────────────────────────────────

# Этап 1 — установка Python зависимостей
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Этап 2 — финальный образ
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ansible \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Python пакеты из builder
COPY --from=builder /install /usr/local

# Код приложения
COPY app/     ./app/

# Ansible плейбуки
COPY ansible/ ./ansible/

RUN mkdir -p /tmp/ansible-runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ANSIBLE_PLAYBOOKS_DIR=/app/ansible

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]