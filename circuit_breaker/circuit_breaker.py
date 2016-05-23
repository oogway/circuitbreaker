import time
import functools
import threading


CLOSED = 0
OPEN = 1
HALF_OPEN = 2


class CircuitBreaker(object):
    def __init__(self, allowed_fails=3, retry_time=30, validation_func=None):
        '''
        Initializes Breaker object

        Args:
            allowed_fails(int): Maximum number of consecutive failures allowed before
                                opening circuit
            retry_time(int): Number of seconds during close period before allowing
                             test request to check if other end of circuit is responsive
            validation_func(func): function to check if return value of wrapped function
                                   is permissible. Must return boolean value
        '''
        self._allowed_fails = allowed_fails
        self.retry_time = retry_time
        self._validation_func = validation_func
        self._lock = threading.Lock()
        self._failure_count = 0
        self._state = CLOSED
        self._half_open_time = 0  # initialize to minimum seconds since epoch

    def _open(self):
        '''Open the circuit breaker and set time for half open'''
        self._state = OPEN
        open_time = time.time()
        self._half_open_time = open_time + self.retry_time

    def _close(self):
        '''Close circuit breaker and reset failure count'''
        self._state = CLOSED
        self._failure_count = 0

    def _half_open(self):
        ''' Set circuit breaker to half open state'''
        self._state = HALF_OPEN

    def _check_state(self):
        '''Check current state of breaker and set half open when possible'''
        if self._state == OPEN:
            now = time.time()
            if now >= self._half_open_time:
                self._half_open()

        return self._state

    def _on_failure(self):
        '''
        Increments failure counter and switches state if allowed_fails is reached
        '''
        self._failure_count += 1
        if self._failure_count >= self._allowed_fails:
            current_state = self._check_state()
            if current_state != OPEN:
                self._open()

    def _on_success(self):
        '''
        Resets failure counter and moves breaker to closed state
        '''
        self._close()

    def _parse_result(self, result):
        '''
        Determine if result of wrapped function is valid

        Args:
            result(object): return value of wrapped function
        '''
        if self._validation_func(result):
            self._on_success()
        else:
            self._on_failure()

    def _call(self, func, *args, **kwargs):
        '''
        Wraps decorated function and watches for successes and failures

        Args:
            func(function): decorated function
            *args: args passed to decorated function
            **kwargs: kwargs passed to decorated function
        '''
        with self._lock:
            current_state = self._check_state()
            if current_state == OPEN:
                return
            try:
                result = func(*args, **kwargs)
            except Exception:
                self._on_failure()
            else:
                if self._validation_func is not None:
                    self._parse_result(result)
                else:
                    self._on_success()

    def __call__(self, func):
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            return self._call(func, *args, **kwargs)

        return wrapped_func
