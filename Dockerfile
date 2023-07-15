FROM python:3.11.4
WORKDIR /data
RUN apt-get update && \
    apt-get install -y git && \
    apt-get install -y tzdata && \
    git clone https://github.com/mijael03/Teltonika-Server.git .
ENV TZ=America/Lima
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Expose port 9980
EXPOSE 9980
#Run the application
ENTRYPOINT ["python", "-u"]
CMD ["snifr.py"]