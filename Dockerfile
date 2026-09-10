# ── Stage 1: Build Frontend ───────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Backend & Runtime ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for C++ compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY python_core.py ./
COPY app.py ./
COPY readme.md ./

# Try compiling C++ native modules (falls back automatically to python_core if any issue)
RUN cmake -S src -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release --target sqlmates_core rtree_core benchmark || true

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Generate sample demo data so the app is immediately usable
RUN python scripts/generate_sample_data.py || true

ENV PORT=8004
ENV HOST=0.0.0.0

EXPOSE 8004

CMD ["sh", "-c", "uvicorn app:app --host ${HOST} --port ${PORT}"]
