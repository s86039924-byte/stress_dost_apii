"""Personalized popup selection with multi-level fallbacks."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from personality_mapper import personality_mapper
from trait_weighting import TraitWeighting, select_popup_with_weighting


class PopupSelector:
    """Select popups using tags, weighting, and safe fallbacks."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.trait_weighting = TraitWeighting(session_id)
        self.last_selected: Dict[str, datetime] = {}
        self.duplicate_buffer_minutes = 30

    def select_popup(
        self,
        personality_vector: Optional[Dict[str, float]],
        category: str,
        popups_by_category: Dict[str, List[Dict]],
        required_type: Optional[str] = None,
    ) -> Optional[Dict]:
        """Select popup for category using 5-level fallback."""
        category_popups = popups_by_category.get(category, [])

        if required_type:
            category_popups = [
                popup for popup in category_popups
                if popup.get('type') == required_type
            ]

        if not category_popups:
            return None

        available = self._filter_recent(category_popups)
        if not available:
            available = category_popups

        selection = self._level1_personality_match(
            available,
            personality_vector,
            category,
        )
        if selection:
            self._record_selection(selection, category)
            return selection

        selection = self._level2_fuzzy_match(available, personality_vector)
        if selection:
            self._record_selection(selection, category)
            return selection

        selection = self._level3_category_match(available, category)
        if selection:
            self._record_selection(selection, category)
            return selection

        selection = self._level4_safe_default(available)
        if selection:
            self._record_selection(selection, category)
            return selection

        if available:
            selection = random.choice(available)
            self._record_selection(selection, category)
            return selection
        return None

    def _level1_personality_match(
        self,
        popup_pool: List[Dict],
        personality_vector: Optional[Dict[str, float]],
        category: str,
    ) -> Optional[Dict]:
        tags = personality_mapper.get_tags_from_personality(
            personality_vector or {},
            category,
        )
        if not tags:
            return None

        matching = [
            popup
            for popup in popup_pool
            if set(popup.get('tags', [])) & set(tags)
        ]
        if not matching:
            return None

        if len(matching) == 1:
            return matching[0]

        return select_popup_with_weighting(
            matching,
            personality_vector,
            {'trait_weighting': self.trait_weighting},
        )

    def _level2_fuzzy_match(
        self,
        popup_pool: List[Dict],
        personality_vector: Optional[Dict[str, float]],
    ) -> Optional[Dict]:
        dominant_tags = personality_mapper.get_dominant_traits_tags(
            personality_vector or {},
            top_n=5,
        )
        if not dominant_tags:
            return None

        scored: List[tuple] = []
        for popup in popup_pool:
            popup_tags = set(popup.get('tags', []))
            matches = sum(1 for tag in dominant_tags if tag in popup_tags)
            if matches:
                scored.append((popup, matches))

        if not scored:
            return None

        scored.sort(key=lambda pair: pair[1], reverse=True)
        top_score = scored[0][1]
        top_matches = [popup for popup, score in scored if score == top_score]
        if len(top_matches) == 1:
            return top_matches[0]

        return select_popup_with_weighting(
            top_matches,
            personality_vector,
            {'trait_weighting': self.trait_weighting},
        )

    def _level3_category_match(
        self,
        popup_pool: List[Dict],
        category: str,
    ) -> Optional[Dict]:
        base_tags = personality_mapper.CATEGORY_TAG_ENRICHMENT.get(
            category,
            {},
        ).get('base_tags', [])
        matches = [
            popup
            for popup in popup_pool
            if any(tag in popup.get('tags', []) for tag in base_tags)
        ]
        return random.choice(matches) if matches else None

    def _level4_safe_default(self, popup_pool: List[Dict]) -> Optional[Dict]:
        safe_tags = [
            'needs_encouragement',
            'supportive',
            'compassionate',
            'confidence_building',
        ]
        matches = [
            popup
            for popup in popup_pool
            if any(tag in popup.get('tags', []) for tag in safe_tags)
        ]
        return random.choice(matches) if matches else None

    def _filter_recent(self, popups: List[Dict]) -> List[Dict]:
        now = datetime.now()
        filtered = []
        for popup in popups:
            popup_id = popup.get('id') or popup.get('text')
            last = self.last_selected.get(popup_id)
            if not last or now - last > timedelta(minutes=self.duplicate_buffer_minutes):
                filtered.append(popup)
        return filtered

    def _record_selection(self, popup: Dict, category: str):
        popup_id = popup.get('id') or popup.get('text')
        self.last_selected[popup_id] = datetime.now()
        self.trait_weighting.record_category_use(category)
