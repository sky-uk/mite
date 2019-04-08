#!/bin/bash -e

docker build -t build_python_mite_packages -f docker/PythonPackages/Dockerfile .
docker tag build_python_mite_packages registry.tools.cosmic.sky/identity/sre/build_python_mite_packages
docker push registry.tools.cosmic.sky/identity/sre/build_python_mite_packages
echo "Python dependencies image built successfully"

docker build -t build_acurl -f docker/Acurl/Dockerfile .
docker tag build_acurl registry.tools.cosmic.sky/identity/sre/build_acurl
docker push registry.tools.cosmic.sky/identity/sre/build_acurl
echo "Acurl image built successfully"

docker build -t mite -f docker/Mite/Dockerfile .
docker tag mite registry.tools.cosmic.sky/identity/sre/mite
docker push registry.tools.cosmic.sky/identity/sre/mite
echo "Mite image built successfully"
