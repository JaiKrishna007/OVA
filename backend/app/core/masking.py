from typing import Optional


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """
    Mask phone number preserving leading digits/prefix and masking the last 5 digits.
    Example: '+91-9845012341' -> '+91-98450*****'
    """
    if not phone:
        return None
    phone_str = str(phone).strip()
    if len(phone_str) > 5:
        return phone_str[:-5] + "*****"
    return "*****"
