from ..config import ConfigManager
from ..runner import Runner
from ..scenario import ScenarioManager
from ..utils import spec_import


def _create_config_manager(opts):
    config_manager = ConfigManager()
    config = spec_import(opts['--config'])()
    for k, v in config.items():
        config_manager.set(k, v)
    for value in opts["--add-to-config"]:
        k, v = value.split(":")
        config_manager.set(k, v)
    return config_manager


def _create_scenario_manager(opts):
    return ScenarioManager(
        start_delay=float(opts['--delay-start-seconds']),
        period=float(opts['--max-loop-delay']),
        spawn_rate=int(opts['--spawn-rate']),
    )


def _create_runner(opts, transport, msg_sender):
    loop_wait_max = float(opts['--max-loop-delay'])
    loop_wait_min = float(opts['--min-loop-delay'])
    max_work = None
    if opts['--runner-max-journeys']:
        max_work = int(opts['--runner-max-journeys'])
    return Runner(
        transport,
        msg_sender,
        loop_wait_min=loop_wait_min,
        loop_wait_max=loop_wait_max,
        max_work=max_work,
        debug=opts['--debugging'],
    )
