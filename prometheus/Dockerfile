FROM prom/prometheus:latest
ADD ./prometheus/prometheus_config_docker.yml /etc/prometheus/prometheus_config_docker.yml
CMD [ "--config.file=/etc/prometheus/prometheus_config_docker.yml" ] 