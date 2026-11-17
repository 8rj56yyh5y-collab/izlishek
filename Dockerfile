# 1) збираємо фронт
FROM node:22-slim AS web
WORKDIR /web
COPY vue-app/package.json vue-app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY vue-app/ ./
RUN npm run build   # → /static/spa

# 2) бекенд
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY main.py .
COPY --from=web /static/spa static/spa
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
