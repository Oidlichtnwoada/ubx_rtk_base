import typing


def get_default_string_value(
    optional_value: typing.Optional[str], default_value: str = ""
) -> str:
    if optional_value is None:
        return default_value
    else:
        return optional_value
