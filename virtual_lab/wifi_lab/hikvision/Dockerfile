FROM nginx:alpine

# Hikvision-style IP camera with vulnerable login
# Simulates: Default credentials, outdated firmware, directory listing

RUN apk add --no-cache apache2-utils

COPY nginx.conf /etc/nginx/nginx.conf
COPY html/ /usr/share/nginx/html/
COPY .htpasswd /etc/nginx/.htpasswd

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
