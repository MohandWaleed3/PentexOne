"""
Network Anomaly Detector
========================

Uses real statistical methods (Z-score, IQR, Jaccard similarity) to
flag devices that deviate from the rest of the network — not just
"if hostname == X" rules.

This is what users see when we say "AI" in the UI. It's basic but
honest unsupervised learning: every signal is reproducible and
explainable, no magic.

Signals computed
----------------
1. port_count_zscore
   Devices with port counts statistically far from the median.
   Anomalous = |z| > 2.0  (≈ 95th percentile).

2. vendor_protocol_rarity
   Devices whose (vendor, protocol) pair is rare in this network.
   Catches "the only Hikvision on a Philips Hue network".

3. risk_outlier
   Devices whose risk score is in the top IQR-outlier band.

4. profile_similarity
   For each device, find its 3 closest neighbours by Jaccard similarity
   over (open_ports, protocol, risk_level). Devices with low similarity
   to anyone are loners — often the most interesting.

All scores return in [0, 1] so the UI can render them as a bar.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Dict, List, Optional, Tuple


def _safe_zscore(value: float, values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.fmean(values)
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0
    if stdev == 0:
        return 0.0
    return (value - mean) / stdev


def _parse_ports(ports_str: Optional[str]) -> List[int]:
    if not ports_str:
        return []
    out = []
    for p in str(ports_str).split(","):
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def analyze_network(devices: List[Dict]) -> Dict:
    """
    devices: list of dicts with keys
        ip, hostname, vendor, protocol, risk_level, risk_score, open_ports
    Returns:
        {
          "anomalies": [{ip, score, reasons, signal_breakdown}],
          "network_stats": {...},
        }
    """
    if not devices:
        return {"anomalies": [], "network_stats": {"device_count": 0}}

    # ── Pre-compute aggregate stats ─────────────────────────────────
    port_lists = [_parse_ports(d.get("open_ports")) for d in devices]
    port_counts = [len(pl) for pl in port_lists]
    risk_scores = [float(d.get("risk_score") or 0) for d in devices]

    vendor_protocol_pairs = [
        (d.get("vendor") or "Unknown", d.get("protocol") or "Unknown")
        for d in devices
    ]
    vp_freq = Counter(vendor_protocol_pairs)

    # IQR for risk score outliers
    risk_q1 = risk_scores[len(risk_scores) // 4] if len(risk_scores) >= 4 else 0
    sorted_rs = sorted(risk_scores)
    n = len(sorted_rs)
    q1 = sorted_rs[n // 4]
    q3 = sorted_rs[(3 * n) // 4]
    iqr = q3 - q1
    risk_outlier_threshold = q3 + 1.5 * iqr if iqr > 0 else max(sorted_rs) + 1

    # ── Per-device analysis ────────────────────────────────────────
    anomalies = []
    for idx, d in enumerate(devices):
        reasons: List[str] = []
        signals: Dict[str, float] = {}

        # Signal 1: port count z-score
        z_ports = _safe_zscore(port_counts[idx], port_counts)
        signals["port_count_zscore"] = round(z_ports, 2)
        if abs(z_ports) > 2.0:
            reasons.append(
                f"Open port count ({port_counts[idx]}) is {abs(z_ports):.1f}σ from network median."
            )

        # Signal 2: vendor/protocol rarity
        pair = vendor_protocol_pairs[idx]
        freq = vp_freq[pair]
        rarity = 1.0 - (freq / len(devices))
        signals["vendor_protocol_rarity"] = round(rarity, 2)
        if rarity > 0.7 and len(devices) >= 4:
            reasons.append(
                f"{pair[0]} on {pair[1]} is rare in this network ({freq}/{len(devices)} devices)."
            )

        # Signal 3: risk outlier
        rs = risk_scores[idx]
        is_risk_outlier = rs > risk_outlier_threshold
        signals["risk_outlier"] = 1.0 if is_risk_outlier else 0.0
        if is_risk_outlier:
            reasons.append(
                f"Risk score {rs:.0f} is an outlier vs. network IQR (Q3+1.5×IQR={risk_outlier_threshold:.0f})."
            )

        # Signal 4: profile similarity (loner detection)
        my_profile = set(port_lists[idx]) | {
            f"PROTO:{d.get('protocol')}",
            f"RISK:{d.get('risk_level')}",
        }
        similarities = []
        for j, other in enumerate(devices):
            if j == idx:
                continue
            other_profile = set(port_lists[j]) | {
                f"PROTO:{other.get('protocol')}",
                f"RISK:{other.get('risk_level')}",
            }
            similarities.append(_jaccard(my_profile, other_profile))
        if similarities:
            top3 = sorted(similarities, reverse=True)[:3]
            avg_top3 = sum(top3) / len(top3)
            signals["profile_similarity"] = round(avg_top3, 2)
            if avg_top3 < 0.3 and len(devices) >= 4:
                reasons.append(
                    f"Profile is dissimilar from rest of network (top-3 Jaccard avg = {avg_top3:.2f})."
                )
        else:
            signals["profile_similarity"] = 1.0

        # Combine into an anomaly score in [0, 1]
        components = [
            min(1.0, abs(z_ports) / 3.0),
            rarity if rarity > 0.7 else 0.0,
            1.0 if is_risk_outlier else 0.0,
            1.0 - signals.get("profile_similarity", 1.0)
                  if signals.get("profile_similarity", 1.0) < 0.3 else 0.0,
        ]
        score = sum(components) / 4.0

        if reasons:
            anomalies.append({
                "ip": d.get("ip"),
                "hostname": d.get("hostname"),
                "vendor": d.get("vendor"),
                "protocol": d.get("protocol"),
                "score": round(score, 2),
                "reasons": reasons,
                "signal_breakdown": signals,
            })

    anomalies.sort(key=lambda a: a["score"], reverse=True)

    return {
        "anomalies": anomalies,
        "network_stats": {
            "device_count": len(devices),
            "median_port_count": statistics.median(port_counts),
            "median_risk_score": statistics.median(risk_scores),
            "risk_outlier_threshold": round(risk_outlier_threshold, 1),
            "unique_vendors": len({v for v, _ in vendor_protocol_pairs}),
            "unique_protocols": len({p for _, p in vendor_protocol_pairs}),
        },
        "method": "z-score + IQR + Jaccard similarity (unsupervised)",
    }
