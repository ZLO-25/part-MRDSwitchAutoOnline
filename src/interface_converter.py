import re
from typing import Optional

# 1) Define a mapping between shorthand and full-form interface names.
INTERFACE_MAP = {
    # "100GbE": "HundredGigabitE",
    # "40GbE":  "FortyGigabit",
    "XGE": "TwentyFiveGigabitEthernet",
    # "10GbE": "Ten-GigabitEthernet",
    # "1GbE": "GigabitEthernet",
}

# Create a reverse mapping for bidirectional lookup (full form to shorthand).
INTERFACE_MAP_REVERSE = {v: k for k, v in INTERFACE_MAP.items()}


def convert_interface(if_name: str, to_full: bool = True) -> Optional[str]:
    """
    Convert an interface name between shorthand and full form.

    Args:
        if_name: The input interface name (e.g., '100GbE1/0/1' or 'HundredGigabitEthernet1/0/1').
        to_full: If True, convert shorthand to full form; if False, convert full form to shorthand.

    Returns:
        The converted interface name if successful, or None if conversion fails.
    """
    map_dict = INTERFACE_MAP if to_full else INTERFACE_MAP_REVERSE

    pattern = re.compile(r"^([^\d]+)(.*)$")
    match = pattern.match(if_name)
    if not match:
        return None

    prefix, suffix = match.groups()
    if prefix not in map_dict:
        return None

    converted_prefix = map_dict[prefix]
    return converted_prefix + suffix


def try_convert_interface(if_name: str) -> Optional[str]:
    """
    Attempt to convert the interface name by first converting from shorthand to full form,
    and if that fails, converting from full form to shorthand.
    If both conversions fail, return None.

    Args:
        if_name: The input interface name.

    Returns:
        The converted interface name if conversion is successful, or None otherwise.
    """
    # Try converting from shorthand to full form.
    result_full = convert_interface(if_name, to_full=True)
    if result_full is not None:
        return result_full

    # If that fails, try converting from full form to shorthand.
    result_short = convert_interface(if_name, to_full=False)
    if result_short is not None:
        return result_short

    # Both conversions failed; return None.
    return None


def main():
    # Test cases
    test_interfaces = [
        # "100GbE1/0/1",             # shorthand with interface number
        # "40GbE2/1/1",              # shorthand with interface number
        # "FortyGigabitEthernet2/2/1",# full form with interface number
        "XGE1/0/1",                     # shorthand, no conversion expected
        "TwentyFiveGigabitEthernet1/0/1", # full form, no conversion expected
        # "TenGigabitEthernet0/1",    # full form example
        # "RandomStuffEthernet1/0"    # conversion should fail
    ]

    for if_name in test_interfaces:
        converted = try_convert_interface(if_name)
        if converted is None:
            print(f"{if_name} -> Conversion failed")
        else:
            print(f"{if_name} -> {converted}")


if __name__ == "__main__":
    main()