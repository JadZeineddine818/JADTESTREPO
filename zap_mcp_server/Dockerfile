FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install fastapi uvicorn requests pydantic

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8003"]