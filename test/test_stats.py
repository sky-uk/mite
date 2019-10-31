from mite.stats import labels_extractor


TXN_MSG = {
        'start_time': 1572604344.7903123,
        'end_time': 1572604346.0693598,
        'had_error': True,
        'type': 'txn',
        'time': 1572604346.0693617,
        'test': 'mite_project.file:scenario',
        'runner_id': 1,
        'journey': 'mite_project.file:journey',
        'context_id': 8,
        'scenario_id': 31,
        'scenario_data_id': 2,
        'transaction': 'txn_name',
        'transaction_id': 3}


def test_labels_extractor_txn_msg():
    extractor = labels_extractor("test journey transaction had_error".split())
    labels = extractor(TXN_MSG)
    assert next(labels) == ('mite_project.file:scenario', 'mite_project.file:journey', 'txn_name', True)


