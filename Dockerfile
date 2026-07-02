# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Collect static files at runtime instead of build time to avoid missing env vars
# Expose port
EXPOSE 8000

# Run collectstatic, database migrations, and boot Gunicorn
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn core.wsgi:application --bind 0.0.0.0:8000"]
