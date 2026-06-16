from .emit import EMIT_HANDLERS, EMIT_TOOLS
from .example import EXAMPLE_HANDLERS, EXAMPLE_TOOLS
from .users import USER_HANDLERS, USER_TOOLS


def all_tools() -> list[dict]:
    return [
        *EXAMPLE_TOOLS,
        *USER_TOOLS,
        *EMIT_TOOLS,
    ]


def all_handlers() -> dict:
    return {
        **EXAMPLE_HANDLERS,
        **USER_HANDLERS,
        **EMIT_HANDLERS,
    }
