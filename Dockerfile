# Stage 1: 编译前端
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python 运行时
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/logs

WORKDIR /app/src

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 默认启动 API 服务器（交易机器人可单独启动）
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
