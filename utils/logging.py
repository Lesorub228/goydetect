from typing import Any, Literal

log_sensitive = False
length_limit = 300


def sensitive(obj: Any) -> Any | Literal["********"]:
    if log_sensitive:
        return obj
    return "********"


def short(obj: Any) -> str:
    return str(obj)[:length_limit]
