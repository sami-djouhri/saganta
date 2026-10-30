from .config import settings
from .models import Asset


PROTECTED_STATES = {"critical", "homelab_active", "daily_use"}


def resale_recommendation(asset: Asset) -> tuple[bool, str | None]:
    """True wenn Verkauf empfohlen: Threshold-Wert UND ungeschützter Status."""
    if asset.usage_status in PROTECTED_STATES:
        return False, f"geschützt durch usage_status={asset.usage_status}"
    if asset.market_value_eur is None:
        return False, "kein Marktwert ermittelt"
    if asset.market_value_eur < settings.resale_threshold_eur:
        return False, (
            f"Marktwert {asset.market_value_eur:.0f} EUR unter Schwelle "
            f"{settings.resale_threshold_eur:.0f} EUR"
        )
    return True, f"Marktwert ~{asset.market_value_eur:.0f} EUR und ungeschützt"
