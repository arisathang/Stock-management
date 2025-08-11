# backend/Dockerfile
# Instructions for building the Python backend container.

# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source code
COPY . .

# Expose the port Flask will run on
EXPOSE 5001

# Command to run the Flask application
CMD ["python", "server.py"]
