from .config import ConfigManager
from .utils import spec_import


def _create_config_manager(opts):
    config_manager = ConfigManager()
    config = spec_import(opts['--config'])()
    for k, v in config.items():
        config_manager.set(k, v)
    for value in opts["--add-to-config"]:
        k, v = value.split(":")
        config_manager.set(k, v)
    return config_manager
