from __future__ import annotations

import numpy as np
import pandas as pd
import ruptures as rpt


def assign_tiers(df: pd.DataFrame, n_tiers: int = 5) -> pd.DataFrame:
    if df.empty:
        out = df.copy()
        out["tier"] = []
        return out

    out = df.copy()
    out["tier"] = np.nan

    for position in out["position"].dropna().unique():
        pos_idx = out[out["position"] == position].sort_values("vorp", ascending=False).index
        values = out.loc[pos_idx, "vorp"].to_numpy(dtype=float)
        if len(values) == 0:
            continue

        signal = values.reshape(-1, 1)
        breakpoints = rpt.Pelt(model="rbf").fit(signal).predict(pen=3)
        segments = [bp for bp in breakpoints if bp <= len(values)]
        if not segments or segments[-1] != len(values):
            segments.append(len(values))

        # Tier assignment by changepoint segment, merged down to n_tiers max.
        tier_ids = np.zeros(len(values), dtype=int)
        start = 0
        for segment_idx, end in enumerate(segments, start=1):
            tier_ids[start:end] = segment_idx
            start = end

        if tier_ids.max() > n_tiers:
            # Compress extra bottom segments into the last tier.
            tier_ids = np.minimum(tier_ids, n_tiers)

        out.loc[pos_idx, "tier"] = tier_ids

    out["tier"] = out["tier"].fillna(n_tiers).astype(int)
    return out
