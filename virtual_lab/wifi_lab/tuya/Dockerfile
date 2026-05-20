FROM python:3.11-alpine

# Tuya Smart Plug simulation
# Vulnerabilities: UPnP exposed, no local auth, device info disclosure

WORKDIR /app
COPY app.py /app/

EXPOSE 80 6668

CMD ["python3", "app.py"]
