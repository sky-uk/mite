#!/usr/bin/env python3

import logging
import os

import psutil

if os.path.dirname(__file__) != "":
    os.chdir(os.path.dirname(__file__))


def deploy_mite():
    deploy_all = psutil.Popen(("docker-compose", "-f", "docker_compose.yml", "up", "-d"))
    if deploy_all.status() in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE):
        logging.error("Failed to run docker compose")


if __name__ == "__main__":
    deploy_mite()
