test_work = [
    (1, 1, "legacy:journeytest1", ("1",)),
    (2, 2, "legacy:journeytest2", ("2",)),
    (3, 3, "legacy:journeytest3", ("3",)),
    (4, 4, "legacy:journeytest3", ("4",)),
    (5, 5, "legacy:journeytest3", ("5",)),
    (6, 6, "legacy:journeytest3", ("6",)),
    (7, 7, "legacy:journeytest3", ("7",)),
]


class DirectRunnerTransportMock:
    def __init__(
        self,
        runner_id=10,
        test_name="mite unit test mock",
        config_list=(("unit_test_mock_value", "x"),),
        work=test_work,
    ):
        # The format of work is:
        # scenario_id, scenario_data_id, journey_spec, args
        self._runner_id = runner_id
        self._test_name = test_name
        self._config_list = config_list
        self._work = work

        self._completed_data = []
        self._sent_work = False
        self._all_done = False

    async def hello(self):
        return self._runner_id, self._test_name, self._config_list

    async def bye(self, runner_id):
        self._all_done = True

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        self._completed_data += completed_data_ids
        to_send = [] if self._sent_work else self._work
        self._sent_work = True
        return to_send, [], True
