FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh && mkdir -p /data/inbox /data/archive /data/failed

ENTRYPOINT ["/startup.sh"]
CMD ["import-daemon"]
