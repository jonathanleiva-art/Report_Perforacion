from copy import deepcopy
from functools import wraps
from pathlib import Path


def _freeze(value):
    if isinstance(value, Path):
        return ("Path", str(value))
    if isinstance(value, dict):
        return tuple(sorted((_freeze(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _clone(value):
    try:
        return deepcopy(value)
    except Exception:
        return value


def _cache_decorator(*, copy_values):
    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (_freeze(args), _freeze(kwargs))
            if key not in cache:
                cache[key] = func(*args, **kwargs)
            return _clone(cache[key]) if copy_values else cache[key]

        def clear():
            cache.clear()

        wrapper.clear = clear
        return wrapper

    return decorator


def cache_data(*args, **_kwargs):
    decorator = _cache_decorator(copy_values=True)
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def cache_resource(*args, **_kwargs):
    decorator = _cache_decorator(copy_values=False)
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator
