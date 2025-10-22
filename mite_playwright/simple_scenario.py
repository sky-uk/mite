"""
Simple Playwright Scenario - Basic test scenario

A simplified scenario class for browser automation tests.
"""

import time
from .simple_runner import SimplePlaywrightRunner


class SimplePlaywrightScenario:
    """Simple scenario for browser automation tests"""
    
    def __init__(self, runner: SimplePlaywrightRunner, name="test"):
        """
        Initialize scenario.
        
        Args:
            runner: SimplePlaywrightRunner instance
            name: Scenario name
        """
        self.runner = runner
        self.name = name
        self.metrics = {}
        self.start_time = None
    
    async def setup(self):
        """Setup scenario"""
        await self.runner.start()
    
    async def teardown(self):
        """Teardown scenario"""
        await self.runner.stop()
    
    async def run(self):
        """Run the scenario"""
        self.start_time = time.time()
        
        try:
            await self.setup()
            await self.execute()
            
            total_time = (time.time() - self.start_time) * 1000
            self.metrics['total_time'] = total_time
            
            print(f"Scenario '{self.name}' completed in {total_time:.2f}ms")
            return self.metrics
            
        except Exception as e:
            print(f"Scenario '{self.name}' failed: {e}")
            raise
        finally:
            await self.teardown()
    
    async def execute(self):
        """Override this method with your test steps"""
        raise NotImplementedError("Implement execute() method")
    
    def log_metric(self, name, value):
        """Log a performance metric"""
        self.metrics[name] = value
        print(f"{name}: {value:.2f}ms")


class SimplePageLoadScenario(SimplePlaywrightScenario):
    """Simple page load test scenario"""
    
    def __init__(self, runner, url, name="page_load"):
        super().__init__(runner, name)
        self.url = url
    
    async def execute(self):
        """Load a page and measure timing"""
        load_time = await self.runner.goto(self.url)
        self.log_metric("page_load_time", load_time)
        
        # Wait for body to be visible
        wait_time = await self.runner.wait_for("body")
        self.log_metric("body_visible_time", wait_time)


class SimpleLoginScenario(SimplePlaywrightScenario):
    """Simple login test scenario"""
    
    def __init__(self, runner, login_url, username, password, name="login"):
        super().__init__(runner, name)
        self.login_url = login_url
        self.username = username
        self.password = password
    
    async def execute(self):
        """Perform login and measure timing"""
        # Navigate to login page
        nav_time = await self.runner.goto(self.login_url)
        self.log_metric("navigation_time", nav_time)
        
        # Fill username
        username_time = await self.runner.fill("#username", self.username)
        self.log_metric("username_fill_time", username_time)
        
        # Fill password
        password_time = await self.runner.fill("#password", self.password)
        self.log_metric("password_fill_time", password_time)
        
        # Click login button
        login_time = await self.runner.click("#login-button")
        self.log_metric("login_click_time", login_time)