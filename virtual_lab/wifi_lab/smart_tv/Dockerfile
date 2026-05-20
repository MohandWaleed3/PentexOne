FROM python:3.11-alpine

# Samsung Smart TV simulation - Guest network device
# Vulnerabilities: DIAL exposed, voice API open, no pairing required

WORKDIR /app
COPY app.py /app/

EXPOSE 80 8001 9197

CMD ["python3", "app.py"]
