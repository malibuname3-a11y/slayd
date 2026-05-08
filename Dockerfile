# Multi-stage build - kichik va tez image
FROM python:3.11-alpine as builder

# Build zarurliklari
RUN apk add --no-cache gcc musl-dev linux-headers

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage - faqat kerakli narsalar
FROM python:3.11-alpine

# Runtime zarurliklari (agar kerak bo'lsa)
RUN apk add --no-cache libffi openssl

WORKDIR /app

# Faqat kerakli fayllar
COPY --from=builder /root/.local /root/.local
COPY bot.py .
COPY config.json .

# PATH sozlash
ENV PATH=/root/.local/bin:$PATH     PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3     CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "bot.py"]
