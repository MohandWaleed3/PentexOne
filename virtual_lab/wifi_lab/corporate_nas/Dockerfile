FROM python:3.11-alpine

# Corporate NAS simulation (Synology-style)
# Vulnerabilities: default creds, SMBv1, anonymous FTP, exposed /etc/shadow

WORKDIR /app
COPY app.py /app/

EXPOSE 80 5000 445 21

CMD ["python3", "app.py"]
