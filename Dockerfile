# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv (preferred package manager)
# Pinning the version for reproducibility, check for newer versions if needed
RUN pip install uv==0.1.41

# Copy the dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# Use --system to install into the system Python, common for containers
# Use --no-cache to reduce layer size (optional)
RUN uv sync --system --no-cache

# Copy the rest of the application code into the container
COPY . .

# Make port 8080 available to the world outside this container
# Cloud Run will map requests to this port based on the PORT env var
EXPOSE 8080

# Define environment variable for the PORT (redundant as Cloud Run sets it, but good practice)
ENV PORT=8080

# Run slack_bot.py when the container launches
# The script is now configured to listen on the port specified by the PORT env var
CMD ["python", "slack_bot.py"]
