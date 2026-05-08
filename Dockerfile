FROM python:3.11-alpine AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-alpine
COPY --from=builder /root/.local /root/.local
COPY bot.py .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "bot.py"]
