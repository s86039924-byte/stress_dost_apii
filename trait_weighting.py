"""Weighted selection utilities for popup personalization."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from personality_mapper import personality_mapper


class TraitWeighting:
    """Track popup usage and weight candidate tags."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.tag_history: Dict[str, List[datetime]] = defaultdict(list)
        self.category_history: Dict[str, List[datetime]] = defaultdict(list)
        self.selected_popups: List[Dict] = []
        self.MIN_TAG_REPEAT_MINUTES = 15
        self.MIN_CATEGORY_REPEAT_MINUTES = 10

    def calculate_tag_weights(
        self,
        candidate_tags: Sequence[str],
        personality_vector: Optional[Dict[str, float]],
    ) -> Dict[str, float]:
        """Score tags using relevance, recency, and variety."""
        if not candidate_tags:
            return {}

        weights: Dict[str, float] = {}
        now = datetime.now()
        for tag in candidate_tags:
            weight = 1.0
            weight *= self._get_personality_weight(tag, personality_vector or {})

            recent_uses = [
                timestamp
                for timestamp in self.tag_history.get(tag, [])
                if now - timestamp < timedelta(minutes=self.MIN_TAG_REPEAT_MINUTES)
            ]
            if recent_uses:
                weight *= 1.0 / (1.0 + len(recent_uses) * 0.5)

            if len(self.tag_history.get(tag, [])) < 2:
                weight *= 1.2

            weights[tag] = max(0.1, weight)

        total = sum(weights.values())
        if total:
            weights = {tag: value / total for tag, value in weights.items()}
        return weights

    def _get_personality_weight(
        self,
        tag: str,
        personality_vector: Dict[str, float],
    ) -> float:
        reverse_map: Dict[str, tuple] = {}
        for dimension, tiers in personality_mapper.TRAIT_TO_TAG_MAPPING.items():
            for tier, tags in tiers.items():
                for mapped_tag in tags:
                    reverse_map.setdefault(mapped_tag, (dimension, tier))

        if tag not in reverse_map:
            return 1.0

        dimension, tier = reverse_map[tag]
        value = personality_vector.get(dimension, 0.5)

        if tier == 'low':
            target = 0.25
        elif tier == 'high':
            target = 0.75
        else:
            target = 0.5

        relevance = 1.0 - abs(value - target) / 0.5
        return max(0.3, relevance)

    def select_weighted_tag(
        self,
        candidate_tags: Sequence[str],
        personality_vector: Optional[Dict[str, float]],
    ) -> Optional[str]:
        """Return a tag sampled using calculated weights."""
        if not candidate_tags:
            return None

        weights = self.calculate_tag_weights(candidate_tags, personality_vector)
        if not weights:
            return random.choice(list(candidate_tags))

        selected = random.choices(
            list(weights.keys()),
            weights=list(weights.values()),
            k=1,
        )[0]
        self.tag_history[selected].append(datetime.now())
        self.selected_popups.append({'tag': selected, 'timestamp': datetime.now()})
        return selected

    def get_variety_score(self) -> float:
        """Compute diversity of delivered tags."""
        if len(self.selected_popups) < 2:
            return 1.0
        total = len(self.selected_popups)
        unique_count = len({entry['tag'] for entry in self.selected_popups})
        return unique_count / total if total else 1.0

    def should_force_variety(self) -> bool:
        """Force variety if repetition detected."""
        if len(self.selected_popups) >= 5:
            recent = [entry['tag'] for entry in self.selected_popups[-5:]]
            if len(set(recent)) <= 2:
                return True
        return self.get_variety_score() < 0.4

    def record_category_use(self, category: str):
        """Track when a popup category is used."""
        self.category_history[category].append(datetime.now())


def select_popup_with_weighting(
    popup_pool: Sequence[Dict],
    personality_vector: Optional[Dict[str, float]],
    session_state: Dict[str, TraitWeighting],
) -> Optional[Dict]:
    """Helper to select a popup using trait weighting."""
    if not popup_pool:
        return None

    weighting = session_state.get('trait_weighting')
    if not weighting:
        return random.choice(list(popup_pool))

    tag_to_popup: Dict[str, Dict] = {}
    all_tags = []

    for popup in popup_pool:
        for tag in popup.get('tags', []):
            all_tags.append(tag)
            tag_to_popup.setdefault(tag, popup)

    if not all_tags:
        return random.choice(list(popup_pool))

    if weighting.should_force_variety():
        rare_tags = [
            tag
            for tag in set(all_tags)
            if len(weighting.tag_history.get(tag, [])) < 2
        ]
        if rare_tags:
            chosen_tag = random.choice(rare_tags)
        else:
            chosen_tag = weighting.select_weighted_tag(
                list(set(all_tags)),
                personality_vector,
            )
    else:
        chosen_tag = weighting.select_weighted_tag(
            list(set(all_tags)),
            personality_vector,
        )

    return tag_to_popup.get(chosen_tag) if chosen_tag else random.choice(list(popup_pool))

