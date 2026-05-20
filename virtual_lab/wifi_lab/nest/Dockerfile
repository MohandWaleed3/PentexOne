FROM python:3.11-alpine

# Google Nest Thermostat simulation
# Vulnerabilities: outdated firmware, debug interface exposed, weak session tokens

WORKDIR /app
COPY app.py /app/

EXPOSE 80 8080

CMD ["python3", "app.py"]
