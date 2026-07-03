# ---- Stage 1: build the Svelte UI ----
FROM node:20-slim AS webbuild
WORKDIR /build
# The web build's predev/prebuild copy-models script reads ../models, so the
# meshes (now under UR/meshes) are placed at /build/models in the build image.
COPY UR/meshes ./models
WORKDIR /build/web
COPY UI/web/package.json UI/web/package-lock.json ./
RUN npm ci
COPY UI/web/ ./
RUN npm run build

# ---- Stage 2: FastAPI backend serving the built UI ----
FROM python:3.11-slim
WORKDIR /app

COPY UI/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY UI/backend/main.py .
# Serve the production Svelte build (index.html + assets + models) as /app/static.
COPY --from=webbuild /build/web/dist ./static

EXPOSE 8080

CMD ["python", "main.py"]
