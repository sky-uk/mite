## Customizing mite docker-compose

The docker-compose is setup to be able to run a separate docker container for each mite component. 


### Running your own API server and performance test

To run mite performance test against an app, the `apiserver` container in the docker-compose.yml can be exchanged with any docker image


For example, provide a dockerfile and run command

```
  apiserver:
    build: 
      context: .
      dockerfile: Dockerfile.api
    command: ["python", "manage.py", "runserver", "8000"]
    ports:
    - "8000:8000"

```

Modify the `demo_req` journey in local/demo.py to send a HTTP request to an endpoint from the custom apiserver

```
Note: The _API_URL listens to port 8000 of the apiserver container by default

_API_URL = "http://localhost:8000" 

@mite_http
async def demo_req(ctx):
    async with ctx.transaction("Custom request"):
        await ctx.http.get(f"{_API_URL}/exampleendpoint")

```

Make sure to build a fresh mite image if there is code changes

## Monitoring 

The docker-compose by default will also spin up a prometheus and grafana instance for viewing mite metrics


- Prometheus: http://localhost:9090/graph
- Grafana: http://localhost:3000/d/2_KG1Va7z/mite-docker?orgId=1 

Use default grafana admin creds (admin/admin)

Note: May need to re-configure datasource on grafana to be prometheus