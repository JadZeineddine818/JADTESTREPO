FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install fastapi uvicorn requests reportlab openai

EXPOSE 8005

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]