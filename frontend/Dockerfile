# frontend/Dockerfile (Fixed)
# This correctly sets up a Node.js environment for a React app.

# Use an official Node.js runtime as the base image
FROM node:18-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy package.json and package-lock.json to leverage Docker's layer caching
COPY package*.json ./

# Install project dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Expose the port the React development server runs on
EXPOSE 3000

# The command to start the React development server
CMD ["npm", "start"]
