import math


def value_to_precision_integers(
    value: float, scale_factor: int = 10**7, decimal_places: int = 2
) -> tuple[int, int]:
    scaled_value = value * scale_factor
    fractional_part, integer_part = math.modf(scaled_value)
    return round(integer_part), round(fractional_part * 10**decimal_places)
