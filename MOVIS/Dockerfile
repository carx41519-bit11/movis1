FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY backend/requirements*.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements-cloud.txt && useradd --uid 10001 --create-home movis && mkdir -p /var/data && chown movis:movis /var/data
COPY backend/ ./backend/
COPY web/ ./web/
USER movis
WORKDIR /app/backend
EXPOSE 8080
CMD ["sh", "-c", "exec gunicorn 'webapp:create_app()' --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -"]
