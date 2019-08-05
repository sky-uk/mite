test_works = [(1, 1, 'legacy:journeytest1', ('1',)),
              (2, 2, 'legacy:journeytest2', ('2',)),
              (3, 3, 'legacy:journeytest3', ('3',)),
              (4, 4, 'legacy:journeytest3', ('4',)),
              (5, 5, 'legacy:journeytest3', ('5',)),
              (6, 6, 'legacy:journeytest3', ('6',)),
              (7, 7, 'legacy:journeytest3', ('7',))
              ]


class DirectRunnerTransportMock():
    def __init__(self):
        self._completed_data = []
        self._sent_work = False
        self._all_done = False

    async def hello(self):
        return 10, 'mite.unit_test:mock', [('unit_test_mock_value', '3')]

    async def bye(self, runner_id):
        self._all_done = True

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        self._completed_data += completed_data_ids
        to_send = test_works if not self._sent_work else []
        self._sent_work = True
        return to_send, [], True
