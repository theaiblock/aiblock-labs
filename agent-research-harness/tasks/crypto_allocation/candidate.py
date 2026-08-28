def allocate(history: dict[str, list[float]]) -> dict[str, float]:
    """Equal-weight baseline; the agent replaces this one function."""
    assets = sorted(history)
    if not assets:
        raise ValueError("history is empty")
    weight = 1.0 / len(assets)
    return {asset: weight for asset in assets}
