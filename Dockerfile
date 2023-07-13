FROM python:3.11.4
WORKDIR /data
RUN apt-get update && \
    apt-get install -y git && \
    git clone https://github.com/mijael03/Teltonika-Server.git .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Expose port 9980
EXPOSE 9980
# Run the application
CMD [ "python", "snifr.py" ]