# Use Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-dotenv

# Copy app files (exclude venv)
COPY .env .env
COPY app.py app.py
COPY static static
COPY templates templates
# Avoid copying unnecessary files like venv

# Expose Flask port
EXPOSE 5000

# Run app with env vars
CMD ["sh", "-c", "source .env && python app.py"]