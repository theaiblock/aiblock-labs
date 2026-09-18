import pandas as pd


def signal(close, volume, universe):
    up = close / close.shift(28) - 1 > 0
    n = universe.sum(axis=1)
    return (up & universe).astype(float).div(n, axis=0).fillna(0.0)
