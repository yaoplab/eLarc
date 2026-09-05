from math import log, sqrt
from phibuilder.phi.constants import PHI, SQRT5

_FIB_CACHE = {0: 0, 1: 1, 2: 1}

def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    if n in _FIB_CACHE:
        return _FIB_CACHE[n]
    k = n // 2
    if n % 2 == 0:
        fk = fibonacci(k)
        fk1 = fibonacci(k + 1)
        result = fk * (2 * fk1 - fk)
    else:
        fk = fibonacci(k)
        fk1 = fibonacci(k + 1)
        result = fk * fk + fk1 * fk1
    _FIB_CACHE[n] = result
    return result

def fibonacci_sequence(start: int = 0, count: int = 20) -> list[int]:
    return [fibonacci(i) for i in range(start, start + count)]

def is_fibonacci(n: int) -> bool:
    if n < 0:
        return False
    a = 5 * n * n + 4
    b = 5 * n * n - 4
    return int(sqrt(a)) ** 2 == a or int(sqrt(b)) ** 2 == b

def nearest_fibonacci(n: int) -> int:
    if n <= 0:
        return 0
    idx = round(log(n * SQRT5) / log(PHI))
    candidate = fibonacci(idx)
    if abs(candidate - n) > abs(fibonacci(idx - 1) - n):
        candidate = fibonacci(idx - 1)
    return candidate

def fib_twin(n: int) -> tuple[int, int]:
    if n <= 0:
        return (0, 0)
    a, b = 0, 1
    while b < n:
        a, b = b, a + b
    return (a, b)
