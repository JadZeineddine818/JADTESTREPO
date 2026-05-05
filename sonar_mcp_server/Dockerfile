FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y wget unzip default-jre && \
    rm -rf /var/lib/apt/lists/*

# Install SonarScanner CLI
RUN wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip sonar-scanner-cli-5.0.1.3006-linux.zip && \
    mv sonar-scanner-5.0.1.3006-linux /opt/sonar-scanner && \
    rm sonar-scanner-cli-5.0.1.3006-linux.zip

# Add SonarScanner to PATH
ENV PATH="/opt/sonar-scanner/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn requests pydantic

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]