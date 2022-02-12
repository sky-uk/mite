up: ## Start all in foreground
	@docker-compose -f ../docker_compose.yml up 

start: ## Start all in background
	@docker-compose -f ../docker_compose.yml up -d 

stop: ## Stop all containers
	@docker-compose -f ../docker_compose.yml stop 

status: ## Show status of containers
	@docker-compose -f ../docker_compose.yml ps

restart: ## Restart all containers
	@docker-compose -f ../docker_compose.yml stop 
	@docker-compose -f ../docker_compose.yml up  -d

logs: ## Show logs for all containers
	@docker-compose -f ../docker_compose.yml logs --tail=100 -f 

clean: ## Clean all data
	@docker-compose -f ../docker_compose.yml down