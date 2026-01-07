FROM apache/spark:3.5.0-python3

USER root

# Install additional Python packages
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create app directory
WORKDIR /opt/spark-app

# Copy application code
COPY . /opt/spark-app/

# Set Python path
ENV PYTHONPATH=/opt/spark-app:$PYTHONPATH

USER spark