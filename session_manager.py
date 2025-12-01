"""Session-level personality tracking with adaptive updates."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from personality_mapper import personality_mapper


class SessionManager:
    """Track latest personality state for a student session."""

    def __init__(self, student_id: str):
        self.student_id = student_id
        self.initial_assessment: Optional[Dict[str, float]] = None
        self.current_personality_vector: Dict[str, float] = {}
        self.current_traits: List[str] = []
        self.trait_last_updated: Optional[datetime] = None
        self.performance_history: List[Dict] = []
        self.trait_update_interval_minutes = 10
        self.popup_count_since_update = 0

    def load_initial_personality(self, personality_vector: Dict[str, float]):
        """Seed the session with the assessment output."""
        self.initial_assessment = personality_vector.copy()
        self.current_personality_vector = personality_vector.copy()
        self.trait_last_updated = datetime.now()
        self._refresh_traits_from_vector()

    def update_personality_from_performance(self, popup_performance: Dict):
        """Update vector after each popup interaction."""
        popup_performance = popup_performance.copy()
        popup_performance['timestamp'] = datetime.now()
        self.performance_history.append(popup_performance)
        self.popup_count_since_update += 1

        should_update = False
        if self.popup_count_since_update >= 10:
            should_update = True
        if self.trait_last_updated and (
            datetime.now() - self.trait_last_updated
        ) > timedelta(minutes=self.trait_update_interval_minutes):
            should_update = True

        if should_update:
            self._adjust_personality_from_performance()
            self._refresh_traits_from_vector()

    def _refresh_traits_from_vector(self):
        self.current_traits = personality_mapper.get_dominant_traits_tags(
            self.current_personality_vector,
            top_n=5,
        )
        self.trait_last_updated = datetime.now()
        self.popup_count_since_update = 0

    def _adjust_personality_from_performance(self):
        if len(self.performance_history) < 3:
            return

        recent = self.performance_history[-10:]
        accuracy = sum(1 for entry in recent if entry.get('correct')) / len(recent)
        response_times = [
            entry.get('response_time', 30) for entry in recent if 'response_time' in entry
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 30

        if accuracy > 0.85:
            self.current_personality_vector['intrinsic_motivation'] = max(
                0.0,
                self.current_personality_vector.get('intrinsic_motivation', 0.5) - 0.05,
            )
            if avg_response_time < 20:
                self.current_personality_vector['impulsivity'] = min(
                    1.0,
                    self.current_personality_vector.get('impulsivity', 0.5) + 0.08,
                )

        if accuracy < 0.5:
            self.current_personality_vector['resilience'] = max(
                0.0,
                self.current_personality_vector.get('resilience', 0.5) - 0.05,
            )
            if accuracy < 0.3:
                self.current_personality_vector['stress_sensitivity'] = min(
                    1.0,
                    self.current_personality_vector.get('stress_sensitivity', 0.5) + 0.08,
                )

        categories: Dict[str, int] = {}
        for entry in recent:
            cat = entry.get('category') or 'unknown'
            categories[cat] = categories.get(cat, 0) + 1

        if len(categories) == 1 and len(recent) >= 5:
            self.current_personality_vector['distraction_resistance'] = max(
                0.0,
                self.current_personality_vector.get('distraction_resistance', 0.5) - 0.05,
            )

        for key, value in list(self.current_personality_vector.items()):
            self.current_personality_vector[key] = max(0.0, min(1.0, value))

    def get_session_state(self) -> Dict:
        """Expose snapshot for other components."""
        return {
            'student_id': self.student_id,
            'initial_personality': self.initial_assessment,
            'current_personality_vector': self.current_personality_vector,
            'current_traits': self.current_traits,
            'trait_last_updated': self.trait_last_updated,
            'popup_count': len(self.performance_history),
            'recent_accuracy': self._calculate_recent_accuracy(),
        }

    def _calculate_recent_accuracy(self) -> float:
        if not self.performance_history:
            return 0.5
        recent = self.performance_history[-5:]
        correct = sum(1 for entry in recent if entry.get('correct'))
        return correct / len(recent)

