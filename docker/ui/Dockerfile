# ---- Stage 1: build the Svelte UI ----
FROM node:20-slim AS webbuild
WORKDIR /build
# The web build's predev/prebuild copy-models script reads ../models, so the
# meshes must sit next to web/ in the build image.
COPY models ./models
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Stage 2: FastAPI backend serving the built UI ----
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py .
# Serve the production Svelte build (index.html + assets + models) as /app/static.
COPY --from=webbuild /build/web/dist ./static

EXPOSE 8080

CMD ["python", "main.py"]
