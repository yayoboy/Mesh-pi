from radio.meshtastic_client import ReconnectPolicy


def test_backoff_sequence():
    policy = ReconnectPolicy(base=1, max_delay=8)
    delays = [policy.next_delay() for _ in range(5)]
    assert delays == [1, 2, 4, 8, 8]


def test_backoff_resets_on_success():
    policy = ReconnectPolicy(base=1, max_delay=8)
    policy.next_delay()
    policy.next_delay()
    policy.reset()
    assert policy.next_delay() == 1


def test_policy_attempt_count():
    policy = ReconnectPolicy(base=1, max_delay=30)
    for _ in range(3):
        policy.next_delay()
    assert policy.attempts == 3


def test_policy_max_delay_capped():
    policy = ReconnectPolicy(base=2, max_delay=10)
    delays = [policy.next_delay() for _ in range(10)]
    assert max(delays) == 10


def test_policy_first_delay_is_base():
    policy = ReconnectPolicy(base=3, max_delay=100)
    assert policy.next_delay() == 3
