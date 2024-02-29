#!/bin/bash
# This script is to run local mite processes with dockerized prometheus and grafana
# TODO: Do this in python

# Make sure to have prometheus and grafana running 
# the prometheus config -> mite/prometheus/prometheus_config_template.yml
# grafana dashboard templates -> mite/grafana/provisioning/grafana_dashboard_template.json
docker-compose -f docker_compose_monitoring.yml up -d

# Run mite stack w/o controller
mite runner --controller-socket=tcp://127.0.0.1:14301 --message-socket=tcp://127.0.0.1:14302 &
mite duplicator --message-socket=tcp://0.0.0.0:14302 tcp://0.0.0.0:14303 &
mite stats --stats-in-socket=tcp://127.0.0.1:14303 --stats-out-socket=tcp://0.0.0.0:14305 --stats-include-processors=mite,mite_http &
mite prometheus_exporter --stats-out-socket=tcp://127.0.0.1:14305 --web-address=0.0.0.0:9301 &

# Start a mock web server
# python -m http.server 8000 &

# Controller Command
# mite controller --controller-socket=tcp://0.0.0.0:14301 --message-socket=tcp://127.0.0.1:14302 local.demo:scenario &