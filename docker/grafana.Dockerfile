FROM grafana/grafana:latest
COPY ./grafana/provisioning /etc/grafana/provisioning
COPY ./grafana/config.ini /etc/grafana/config.ini