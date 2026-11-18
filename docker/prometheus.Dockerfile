FROM prom/prometheus:latest
COPY ./prometheus/prometheus_config_docker.yml /etc/prometheus/prometheus_config_docker.yml
CMD [ "--config.file=/etc/prometheus/prometheus_config_docker.yml" ] 