import unittest
import time
import logging

import circuit_breaker


logging.disable(logging.CRITICAL)


DEFAULT_FAILS = 3
DEFAULT_RETRY = 1
DEFAULT_OPEN_CIRCUIT_THREASHOLD = 5


def validation_stub(number):
    return number > 0


def raises_something(exc):
    raise exc


class TestBreaker(unittest.TestCase):
    def setUp(self):
        self.breaker = circuit_breaker.circuit_breaker(
            allowed_fails=DEFAULT_FAILS,
            retry_time=DEFAULT_RETRY,
            retry_after=DEFAULT_OPEN_CIRCUIT_THREASHOLD,
            validation_func=None
        )
        self.breaker_with_validation = circuit_breaker.circuit_breaker(
            allowed_fails=DEFAULT_FAILS,
            retry_time=DEFAULT_RETRY,
            validation_func=validation_stub
        )
        self.breaker_with_allowed = circuit_breaker.circuit_breaker(
            allowed_exceptions=[AttributeError]
        )
        self.breaker_with_fail_exc = circuit_breaker.circuit_breaker(
            failure_exceptions=[KeyError]
        )

    def test_open_transition(self):
        breaker = self.breaker
        for i in range(DEFAULT_FAILS):
            breaker._on_failure()
        self.assertEqual(breaker._state, circuit_breaker.OPEN)
        self.assertEqual(breaker._failure_count, DEFAULT_FAILS)

    def test_success(self):
        breaker = self.breaker
        for i in range(DEFAULT_FAILS - 1):
            breaker._on_failure()
        self.assertEqual(breaker._state, circuit_breaker.CLOSED)
        self.assertEqual(breaker._failure_count, DEFAULT_FAILS - 1)

        breaker._on_success()
        self.assertEqual(breaker._state, circuit_breaker.CLOSED)
        self.assertEqual(breaker._failure_count, 0)

    def test_half_open(self):
        breaker = self.breaker
        for i in range(DEFAULT_FAILS):
            breaker._on_failure()
        self.assertEqual(breaker._state, circuit_breaker.OPEN)

        time.sleep(DEFAULT_RETRY)
        breaker._check_state()
        self.assertEqual(breaker._state, circuit_breaker.HALF_OPEN)

    def test_open_threashold(self):
        breaker = self.breaker
        breaker._close()
        for i in range(DEFAULT_FAILS):
            breaker._on_failure()
        self.assertEqual(breaker._state, circuit_breaker.OPEN)

        for i in range(DEFAULT_OPEN_CIRCUIT_THREASHOLD):
            try:
                breaker._call(raises_something, KeyError())
            except Exception:
                pass
        breaker._check_state()
        self.assertEqual(breaker._state, circuit_breaker.HALF_OPEN)

    def test_validation_func(self):
        breaker = self.breaker_with_validation
        fake_result = 0
        breaker._parse_result(fake_result)
        self.assertEqual(breaker._failure_count, 1)
        # breaker should reset count upon success
        fake_result = 1
        breaker._parse_result(fake_result)
        self.assertEqual(breaker._failure_count, 0)

    def test_no_validation_func(self):
        breaker = self.breaker
        fake_result = 0
        breaker._parse_result(fake_result)
        self.assertEqual(breaker._failure_count, 0)
        fake_result = 1
        breaker._parse_result(fake_result)
        self.assertEqual(breaker._failure_count, 0)

    def test_parse_allowed_exc(self):
        breaker = self.breaker_with_allowed
        breaker._call(raises_something, KeyError())
        self.assertEqual(breaker._failure_count, 1)
        breaker._call(raises_something, AttributeError())
        # not a success, but not a failure either
        self.assertEqual(breaker._failure_count, 1)

    def test_parse_failure_exc(self):
        breaker = self.breaker_with_fail_exc
        breaker._call(raises_something, KeyError())
        self.assertEqual(breaker._failure_count, 1)
        breaker._call(raises_something, AttributeError())
        # not a success, but not a failure either
        self.assertEqual(breaker._failure_count, 1)

    def test_handles_child_exc(self):
        class TestException(AttributeError):
            pass
        breaker = self.breaker_with_allowed
        breaker._call(raises_something, TestException())
        self.assertEqual(breaker._failure_count, 0)

    def test_init_failure(self):
        args = []
        kwargs = {
            "allowed_fails": DEFAULT_FAILS,
            "retry_time": DEFAULT_RETRY,
            "allowed_exceptions": [ValueError, AttributeError],
            "failure_exceptions": [KeyError]
        }
        self.assertRaises(ValueError, circuit_breaker.circuit_breaker, *args,
                          **kwargs)


if __name__ == '__main__':
    unittest.main()
