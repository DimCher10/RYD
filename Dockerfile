FROM python:3.14-slim
WORKDIR /app
COPY server.py ./
COPY public ./public
RUN mkdir -p /app/data
ENV HOST=0.0.0.0 PORT=8000 RYD_DB_PATH=/app/data/ryd.db
EXPOSE 8000
VOLUME ["/app/data"]
CMD ["python", "server.py"]
