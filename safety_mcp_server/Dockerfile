FROM python:3.11-slim

WORKDIR /app

# Install safety
RUN pip install safety fastapi uvicorn requests pydantic

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8004"]