# Elvis POS System Deployment

This document provides instructions for deploying the Elvis POS system on a VPS.

## VPS Deployment

1. **Provision a VPS**: Set up a VPS with a suitable operating system, such as Ubuntu 20.04 LTS.
2. **Install Dependencies**: Install the necessary dependencies, including Python, Node.js, and Docker.
3. **Clone the Repository**: Clone the Elvis POS system repository to the VPS: `git clone https://github.com/zjedzit/elvis.git`
4. **Build and Run the Docker Container**: Navigate to the project directory and build the Docker container: `cd elvis && docker build -t elvis-app .`. Then, run the container: `docker run -d -p 8000:8000 elvis-app`.
5. **Configure the PostgreSQL Database**: Set up a PostgreSQL database for the Elvis POS system and configure the connection details in the application's configuration files.
6. **Verify the Deployment**: Open the Expo interface in your browser: `http://<VPS_IP_ADDRESS>:8000/wydawka`.

## Local Edge Node (Lenovo T520)

For local deployments (e.g. food truck, on-premise POS), the system runs on a **Lenovo T520** as an edge node:

1. **Install Docker** on the T520 with Ubuntu/Debian.
2. **Clone the Repository**: `git clone https://github.com/zjedzit/elvis.git`
3. **Build and Run**: `cd elvis && docker build -t elvis-app . && docker run -d -p 8080:8080 elvis-app`
4. **Configure Database**: Set up PostgreSQL and configure `.env` with connection details.

For both VPS and local edge deployments, ensure that the necessary hardware components, such as the payment terminal and fiscal printer, are properly connected and configured.

If you encounter any issues during the deployment process, please refer to the project's [README.md](README.md) file or open an issue on the [GitHub repository](https://github.com/zjedzit/elvis).