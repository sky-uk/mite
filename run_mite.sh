#!/bin/bash
# This script is to run local mite processes with dockerized prometheus and grafana
# TODO: Do this in python

# Make sure to have prometheus and grafana running 
# the prometheus config -> mite/prometheus_config_template.yml
# grafana dashboard templates -> mite/grafana_dashboard_template.json
docker-compose -f docker_compose_monitoring.yml up -d

# Run mite stack w/o controller
mite runner --controller-socket=tcp://0.0.0.0:14301 --message-socket=tcp://0.0.0.0:14302 &
mite duplicator --message-socket=tcp://0.0.0.0:14302 tcp://0.0.0.0:14303 &
mite stats --stats-in-socket=tcp://0.0.0.0:14303 --stats-out-socket=tcp://0.0.0.0:14305 --stats-include-processors=mite,mite_http &
mite prometheus_exporter --stats-out-socket=tcp://0.0.0.0:14305 --web-address=10.10.10.75:9301 &
# mite controller --controller-socket=tcp://0.0.0.0:14301 --message-socket=tcp://10.11.12.13:14302 local.demo:scenario &