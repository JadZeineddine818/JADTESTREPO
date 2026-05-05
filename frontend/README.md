# FYP AI Secure Orchestrator Dashboard



---

# Project Description

This project is a frontend dashboard built using **React**, **TypeScript**, and **Vite**.  
It provides a modern UI for managing and visualizing system data.

The application is fully **Dockerized** and runs inside a container using **Nginx** as a production web server.

---

##Tech Stack

- React
- TypeScript
- Vite
- Docker
- Nginx (Production Server)

---

 Dockerization Details

The application uses a **multi-stage Docker build**:

1. **Build Stage**
   - Uses `node:20-alpine`
   - Installs dependencies
   - Builds the Vite production files

2. Production Stage
   - Uses `nginx:alpine`
   - Serves the built application
   - Configured to support React Router

---

 How to Run the Project 

1 Build the Docker Image

```bash
docker build -t mariane-app .

2- Run the docker container
docker run -p 8080:80 mariane-app

3- open in browser
http://localhost:8080