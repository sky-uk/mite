import asyncio
import functools
import logging
from itertools import count

import ipdb

from .context import Context
from .utils import spec_import

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def spec_import_cached(journey_spec):
    return spec_import(journey_spec)


class Runner:
    def __init__(
        self, transport, msg_sender, loop_wait_max=0.5, max_work=None, debug=False,
    ):
        self._transport = transport
        self._msg_sender = msg_sender
        self._loop_wait_max = loop_wait_max
        self._max_work = max_work
        self._debug = debug
        self.initialize_run_variables()

    def initialize_run_variables(self):
        self.config = {}
        self.runner_id = None
        self.test_name = None
        self.context_id_gen = count(1)
        self.work = {}
        self.stopping = False

    def _inc_work(self, id):
        if id in self._work:
            self.work[id] += 1
        else:
            self.work[id] = 1

    def _dec_work(self, id):
        self.work[id] -= 1
        if self.work[id] == 0:
            del self.work[id]

    def should_stop(self):
        return self.stopping

    async def run(self):
        if self.runner_id is not None:
            raise Exception("Runner.run() called while already running")
        self.runner_id, self.test_name, config_list = await self._transport.hello()
        self.config.update(config_list)
        logger.debug("Entering run loop")

        completed_data_ids = []
        pending = []
        while not self.stopping or self.work:
            new_work, config_list, self.stopping = await self._transport.request_work(
                self.runner_id,
                self.work,
                completed_data_ids,
                self._max_work if not self.stopping else 0,
            )
            self.config.update(config_list)
            for work_item in new_work:
                scenario_id = work_item[0]
                self._inc_work(scenario_id)
                pending.append(asyncio.create_task(self.do_work, *work_item))
            await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED, timeout=self._loop_wait_max
            )
            # In principle, we could use the result of asyncio.wait to get the
            # list of done coroutines.  But I think there's a subtle reason
            # not to.  I think with FIRST_COMPLETED we will get a single
            # result in the done set.  But we won't resume execution until
            # it's our turn, during which time more coroutines might have
            # completed.  So we should instead filter for doneness when
            # control returns to us, and not trust the (possibly outdated)
            # ersult of the wait function.  Note, I haven't teested this
            # behavior experimentally, just reasonsed about it...
            done = [x for x in pending if x.done()]
            pending = [x for x in pending if not x.done()]
            completed_data_ids = []
            for x in done:
                scenario_id, scenario_data_id = x.result()
                self._dec_work(scenario_id)
                if scenario_data_id is not None:
                    completed_data_ids.append((scenario_id, scenario_data_id))

        # One last time, to send the last batch of results
        await self._transport.request_work(
            self.runner_id, self.work, completed_data_ids, 0
        )
        await self._transport.bye(self.runner_id)

    async def _execute(self, scenario_id, scenario_data_id, journey_spec, args):
        logger.debug(
            'Runner._execute starting scenario_id=%r scenario_data_id=%r journey_spec=%r args=%r',
            scenario_id,
            scenario_data_id,
            journey_spec,
            args,
        )
        id_data = {
            'test': self.test_name,
            'runner_id': self.runner_id,
            'journey': journey_spec,
            'context_id': next(self.context_id_gen),
            'scenario_id': scenario_id,
            'scenario_data_id': scenario_data_id,
        }
        context = Context(
            self._msg_sender,
            self.config,
            id_data=id_data,
            should_stop_func=self.should_stop,
            debug=self._debug,
        )
        journey = spec_import_cached(journey_spec)
        try:
            async with context.transaction('__root__'):
                if args is None:
                    await journey(context)
                else:
                    await journey(context, *args)
        except Exception as e:
            if not getattr(e, "handled", False):
                if self._debug:
                    ipdb.set_trace()
                    raise
        return scenario_id, scenario_data_id
