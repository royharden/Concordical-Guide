FROM node:22.16.0-bookworm-slim@sha256:048ed02c5fd52e86fda6fbd2f6a76cf0d4492fd6c6fee9e2c463ed5108da0e34 AS web-build
WORKDIR /build
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/index.html app/tsconfig.json ./
COPY app/src ./src
RUN npm run build

FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 CG_BIND=0.0.0.0 CG_DATA_DIR=/data/generated
WORKDIR /app
RUN groupadd --gid 10001 cg && useradd --uid 10001 --gid cg --no-create-home cg \
    && mkdir -p /var/lib/cg/userdata && chown 10001:10001 /var/lib/cg/userdata
COPY --from=web-build /build/dist /app/app/dist
COPY scripts/serve_reader.py /app/scripts/serve_reader.py
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz',timeout=3).read()"
CMD ["python", "scripts/serve_reader.py"]
