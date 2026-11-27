from functools import wraps

def mite_ui_wrapper(component_type: str):
    """
    Decorator to mark mite components by type for AST parsing.
    
    Args:
        component_type: Type of component ('journey', 'scenario', 'datapool', 'config')
    
    Usage:
        @mite_ui_wrapper('journey')
        def my_test_journey():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Add attribute access for variables
class _MiteVariableWrapper:
    """Helper class to support attribute-based variable decoration"""
    
    @staticmethod
    def journey(value):
        return value
    
    @staticmethod
    def scenario(value):
        return value
    
    @staticmethod
    def datapool(value):
        return value
    
    @staticmethod
    def config(value):
        return value

# Attach the variable wrapper to mite_ui_wrapper
mite_ui_wrapper.journey = _MiteVariableWrapper.journey
mite_ui_wrapper.scenario = _MiteVariableWrapper.scenario
mite_ui_wrapper.datapool = _MiteVariableWrapper.datapool
mite_ui_wrapper.config = _MiteVariableWrapper.config