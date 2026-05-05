AISecureOrch
bel users->ali->.cursor->mcp.json

1. System Architecture

The system is composed of the following Docker services:

AISecureOrch – Main Python orchestration engine

SonarQube – Static code analysis platform

OWASP ZAP – Dynamic security testing tool

Bandit and Safety are installed inside the AISecureOrch container.

Architecture Flow

User Input
↓
AISecureOrch (Orchestrator)
↓
Security Tools (Bandit / Safety / SonarQube / ZAP)
↓
Aggregator
↓
AI Analysis Engine
↓
Final Security Report

All services communicate through Docker’s internal network.

2. Requirements

Before running the project, ensure the following are installed:

Docker

Docker Compose

Internet connection (required for first-time image download)

No additional software installation is required.
No manual setup of SonarQube, ZAP, Bandit, or Safety is needed.

3. Installation & Execution
Step 1 – Clone the Repository
git clone https://github.com/YOUR_USERNAME/AISecureOrch.git
cd AISecureOrch

Step 2 – Build and Start All Services
docker-compose up --build

This will:

Build the AISecureOrch container

Pull SonarQube and ZAP images

Start all services

Initialize the internal Docker network

This step may take time on first run due to image downloads.

Leave this terminal running

Step 3 – Run the Application

Open a new terminal inside the project directory and execute:
docker exec -it aisecureorch python main.py

Step 4 – Provide Input

You will see:

Enter input (URL, file, or question):

Inside Docker, use:

/app → to analyze the full project

A URL → to trigger dynamic testing

A security question → for AI-only analysis
The system will:

Run relevant security tools

Aggregate findings

Generate an AI-based final report

4. Deployment Model

AISecureOrch is fully containerized.

This ensures:

Environment consistency across machines

No dependency conflicts

No manual tool installation

Reproducible results

To run on another laptop:

Install Docker

Clone the repository

Run docker-compose up --build

No additional setup is required.