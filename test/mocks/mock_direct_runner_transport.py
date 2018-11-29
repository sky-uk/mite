test_works = [(1, 1, 'test.legacy:journeytest1', ('1',)),
              (2, 2, 'test.legacy:journeytest2', ('2',)),
              (3, 3, 'test.legacy:journeytest3', ('3',)),
              (4, 4, 'test.legacy:journeytest3', ('4',)),
              (5, 5, 'test.legacy:journeytest3', ('5',)),
              (6, 6, 'test.legacy:journeytest3', ('6',)),
              (7, 7, 'test.legacy:journeytest3', ('7',))
              ]


class DirectRunnerTransportMock():
    def __init__(self):
        self._completed_data = None

    async def hello(self):
        return 10, 'mite.unit_test:mock', [('unit_test_mock_value', '3')]

    async def bye(self, runner_id):
        pass

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        self._completed_data = completed_data_ids
        self._current_work = current_work
        return test_works, [], True
