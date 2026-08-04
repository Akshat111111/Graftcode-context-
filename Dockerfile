FROM python:3.12-slim

LABEL maintainer="Graftcode Demo"
LABEL description="Python Request Context Demo — Graftcode Context Library"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Add src to PYTHONPATH so graftcode package is importable
ENV PYTHONPATH=/app/src

# Run with uvicorn
CMD ["uvicorn", "src.service:app", "--host", "0.0.0.0", "--port", "8000"]
