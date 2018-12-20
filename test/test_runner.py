import pytest
from mite.runner import Runner

from mocks.mock_direct_runner_transport import DirectRunnerTransportMock
from mocks.mock_direct_receiver import DirectReceiverMock
from mocks.mock_recorder_msg_http import setup_mock_msg_processors


# Inside the runner the directRunnerTransport request the work, what it will receive it should be similar to:
#     [(1, 1, 'test.legacy:journeytest1', ('1',)),
#      (2, 2, 'test.legacy:journeytest2', ('2',)),
#      (...)
#      (7, 7, 'test.legacy:journeytest3', ('7',))]
# During the completition of the received work the runner will populate the "transport._completed_data".
# Because the lasta values used are "(7, 7, 'test.legacy:journeytest3', ('7',))"
# after the last cycle there will be for sure the value (7,7) in the list.
# If not, that means that the runner didin't compute all the works that received


@pytest.mark.asyncio
async def test_runnner_run():
    transport = DirectRunnerTransportMock()
    receiver = DirectReceiverMock()
    setup_mock_msg_processors(receiver)
    for i in range(10):
        runner = Runner(transport, receiver)
        await runner.run()
        print(transport._completed_data)
        assert (7, 7) in transport._completed_data
