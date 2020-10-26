import pytest
from mocks.mock_direct_runner_transport import DirectRunnerTransportMock
from mocks.mock_sender import SenderMock

from mite import MiteError
from mite.runner import Runner

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
    for i in range(10):
        transport = DirectRunnerTransportMock()
        runner = Runner(transport, SenderMock().send)
        while not transport._all_done:
            await runner.run()
        assert (7, 7) in transport._completed_data


async def exception_journey(ctx):
    raise Exception("test")


@pytest.mark.asyncio
async def test_runner_exception():
    transport = DirectRunnerTransportMock(
        work=[(1, 1, "test_runner:exception_journey", ())]
    )
    sender = SenderMock()
    runner = Runner(transport, sender.send)
    while not transport._all_done:
        await runner.run()
    for message in sender.messages:
        if message['type'] == 'exception':
            print(message)
            assert message['ex_type'] == "Exception"
            assert message['message'] == "Exception: test"
            break
    else:
        assert False, "Exception message was not sent"


async def mite_error_journey(ctx):
    raise MiteError("test")


@pytest.mark.asyncio
async def test_runner_mite_error():
    transport = DirectRunnerTransportMock(
        work=[(1, 1, "test_runner:mite_error_journey", ())]
    )
    sender = SenderMock()
    runner = Runner(transport, sender.send)
    while not transport._all_done:
        await runner.run()
    for message in sender.messages:
        if message['type'] == 'error':
            print(message)
            assert message['message'] == "mite.exceptions.MiteError: test"
            break
    else:
        assert False, "Exception message was not sent"
