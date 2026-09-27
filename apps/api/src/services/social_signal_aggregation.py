"""Deterministic, privacy-preserving aggregation of normalized social signals."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from src.adapters.social_signals import NormalizedSocialSignal, SocialSeverity, SocialTopic
from src.schemas.social_signals import SocialSignalClusterResponse


def aggregate_social_signals(
    signals: list[NormalizedSocialSignal],
    *,
    area_name: str,
    latitude: float,
    longitude: float,
    half_life_hours: float,
    now: datetime | None = None,
) -> list[SocialSignalClusterResponse]:
    """Produce one area-level cluster per topic; never expose post-level data."""
    current_time = now or datetime.now(UTC)
    grouped: dict[SocialTopic, list[NormalizedSocialSignal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.topic].append(signal)

    clusters: list[SocialSignalClusterResponse] = []
    for topic, group in grouped.items():
        deduplicated = {signal.deduplication_key: signal for signal in group}
        items = list(deduplicated.values())
        if not items:
            continue
        source_count = len({signal.source_fingerprint for signal in items})
        age_weights = []
        for signal in items:
            age_hours = max(0.0, (current_time - signal.occurred_at).total_seconds() / 3600)
            age_weights.append(math.exp(-math.log(2) * age_hours / half_life_hours))
        freshness = sum(age_weights) / len(age_weights)
        classification = sum(signal.classification_confidence for signal in items) / len(items)
        corroboration = min(1.0, 0.45 + (0.12 * max(0, source_count - 1)))
        confidence = max(0.0, min(1.0, classification * corroboration * (0.6 + 0.4 * freshness)))

        severity_counts = Counter(signal.severity for signal in items)
        severity_rank = {SocialSeverity.LOW: 0, SocialSeverity.MODERATE: 1, SocialSeverity.HIGH: 2}
        severity = max(SocialSeverity, key=lambda value: (severity_counts[value], severity_rank[value]))
        trend = _trend(items, current_time)
        key = f"{area_name.casefold()}|{topic.value}|{latitude:.3f}|{longitude:.3f}"
        cluster_id = hashlib.sha256(key.encode()).hexdigest()[:20]
        clusters.append(
            SocialSignalClusterResponse(
                id=cluster_id,
                topic=topic,
                location_name=area_name,
                latitude=latitude,
                longitude=longitude,
                signal_count=len(items),
                independent_source_count=source_count,
                confidence=round(confidence, 3),
                severity=severity,
                trend=trend,
                newest_signal_at=max(signal.occurred_at for signal in items),
                source_platforms=["bluesky"],
            )
        )
    return sorted(clusters, key=lambda cluster: (-cluster.signal_count, cluster.topic.value))


def _trend(
    signals: list[NormalizedSocialSignal], now: datetime
) -> Literal["rising", "steady", "falling", "insufficient_data"]:
    """Compare two short windows; suppress trend claims for sparse samples."""
    if len(signals) < 5:
        return "insufficient_data"
    recent_start = now - timedelta(hours=2)
    previous_start = now - timedelta(hours=4)
    recent = sum(signal.occurred_at >= recent_start for signal in signals)
    previous = sum(previous_start <= signal.occurred_at < recent_start for signal in signals)
    if recent >= previous + 2:
        return "rising"
    if previous >= recent + 2:
        return "falling"
    return "steady"
