"""Map personality dimensions into reusable popup tags."""

from typing import Dict, List, Optional


class PersonalityMapper:
    """Convert continuous personality vectors into descriptive tags."""

    TRAIT_TO_TAG_MAPPING: Dict[str, Dict[str, List[str]]] = {
        'stress_sensitivity': {
            'low': ['calm_under_pressure', 'composed', 'resilient'],
            'medium': ['manageable_stress', 'adaptive', 'balanced'],
            'high': ['anxious_response', 'needs_calm', 'needs_support'],
        },
        'analytical_thinking': {
            'low': ['intuitive_learner', 'big_picture', 'creative'],
            'medium': ['balanced_analysis', 'methodical', 'structured'],
            'high': ['detail_oriented', 'systematic', 'logical'],
        },
        'social_preference': {
            'low': ['independent', 'solo_work', 'introverted'],
            'medium': ['selective_social', 'flexible', 'balanced_social'],
            'high': ['collaborative', 'group_oriented', 'extroverted'],
        },
        'intrinsic_motivation': {
            'low': ['extrinsic_driven', 'grade_focused', 'reward_motivated'],
            'medium': ['balanced_motivation', 'mixed_drivers', 'flexible'],
            'high': ['intrinsic_driven', 'mastery_focused', 'learning_oriented'],
        },
        'resilience': {
            'low': ['fragile_to_setbacks', 'needs_encouragement', 'recovery_support'],
            'medium': ['moderate_resilience', 'recovers_with_help', 'adaptable'],
            'high': ['bounces_back', 'self_recovering', 'strong_resilience'],
        },
        'self_confidence': {
            'low': ['low_confidence', 'self_doubt', 'confidence_building'],
            'medium': ['moderate_confidence', 'situational_confidence', 'developing'],
            'high': ['high_confidence', 'capable', 'self_assured'],
        },
        'planning_tendency': {
            'low': ['spontaneous', 'flexible', 'improviser'],
            'medium': ['balanced_planning', 'adaptive_planning', 'flexible_structure'],
            'high': ['organized', 'structured', 'planner'],
        },
        'openness_to_feedback': {
            'low': ['defensive', 'resistant', 'fixed_mindset'],
            'medium': ['receptive_with_caution', 'growth_oriented', 'learner'],
            'high': ['open_to_feedback', 'growth_mindset', 'seeker_of_input'],
        },
        'impulsivity': {
            'low': ['deliberate', 'thoughtful', 'careful'],
            'medium': ['balanced_pace', 'measured', 'considered'],
            'high': ['impulsive', 'rushing', 'needs_slowdown'],
        },
        'time_awareness': {
            'low': ['poor_time_sense', 'panic_at_end', 'needs_timing'],
            'medium': ['adequate_time_sense', 'manageable_awareness', 'improving'],
            'high': ['excellent_timer', 'time_aware', 'strategic_pacing'],
        },
        'distraction_resistance': {
            'low': ['easily_distracted', 'needs_focus_support', 'focus_help'],
            'medium': ['moderate_focus', 'situational_focus', 'variable_focus'],
            'high': ['excellent_focus', 'deep_focus', 'flow_capable'],
        },
    }

    CATEGORY_TAG_ENRICHMENT: Dict[str, Dict[str, List[str]]] = {
        'thoughts': {
            'base_tags': ['analytical', 'logical', 'conceptual'],
            'stress_sensitive_add': ['needs_simplification', 'step_by_step'],
            'confident_add': ['challenge_worthy', 'advanced'],
            'analytical_add': ['deep_dive', 'explanation'],
            'intuitive_add': ['pattern_recognition', 'big_picture'],
        },
        'frustration': {
            'base_tags': ['persistence', 'resilience', 'encouragement'],
            'low_resilience_add': ['compassionate', 'supportive', 'confidence_building'],
            'high_resilience_add': ['motivating', 'challenge_reframing'],
            'stress_sensitive_add': ['calm', 'reassuring', 'manageable'],
            'confident_add': ['capability_reminder', 'strength_focus'],
        },
        'fear': {
            'base_tags': ['reassurance', 'confidence_building', 'support'],
            'stress_sensitive_add': ['calming', 'grounding', 'breathing'],
            'low_confidence_add': ['capable_reminder', 'success_story'],
            'resilient_add': ['challenge_reframe', 'strength_building'],
            'intrinsic_motivation_add': ['purpose_reminder', 'learning_value'],
        },
    }

    def __init__(self):
        self.trait_cache: Dict[str, List[str]] = {}

    def get_tags_from_personality(
        self,
        personality_vector: Optional[Dict[str, float]],
        category: Optional[str] = None,
    ) -> List[str]:
        """Convert personality vector into ordered tags."""
        if not personality_vector:
            personality_vector = {}

        tags: List[str] = []
        for dimension, value in personality_vector.items():
            mapping = self.TRAIT_TO_TAG_MAPPING.get(dimension)
            if not mapping:
                continue
            if value < 0.33:
                tier = 'low'
            elif value < 0.67:
                tier = 'medium'
            else:
                tier = 'high'
            tags.extend(mapping.get(tier, []))

        if category and category in self.CATEGORY_TAG_ENRICHMENT:
            enrichment = self.CATEGORY_TAG_ENRICHMENT[category]
            tags.extend(enrichment.get('base_tags', []))

            stress_value = personality_vector.get('stress_sensitivity', 0.5)
            confidence_value = personality_vector.get('self_confidence', 0.5)
            resilience_value = personality_vector.get('resilience', 0.5)
            analytical_value = personality_vector.get('analytical_thinking', 0.5)

            if stress_value > 0.7:
                tags.extend(enrichment.get('stress_sensitive_add', []))
            if confidence_value > 0.7:
                tags.extend(enrichment.get('confident_add', []))
            if resilience_value < 0.3:
                tags.extend(enrichment.get('low_resilience_add', []))
            if analytical_value > 0.7:
                tags.extend(enrichment.get('analytical_add', []))
            if analytical_value < 0.33:
                tags.extend(enrichment.get('intuitive_add', []))
            if category == 'fear' and confidence_value < 0.3:
                tags.extend(enrichment.get('low_confidence_add', []))
            if category == 'fear' and resilience_value > 0.7:
                tags.extend(enrichment.get('resilient_add', []))
            if category == 'fear' and personality_vector.get('intrinsic_motivation', 0.5) > 0.7:
                tags.extend(enrichment.get('intrinsic_motivation_add', []))

        unique_tags: List[str] = []
        seen = set()
        for tag in tags:
            if tag not in seen:
                unique_tags.append(tag)
                seen.add(tag)
        return unique_tags

    def map_trait_name_to_tags(self, trait_name: str) -> List[str]:
        """Map arbitrary trait names to standardized tags."""
        if not trait_name:
            return ['needs_support']

        for tiers in self.TRAIT_TO_TAG_MAPPING.values():
            for tags in tiers.values():
                if trait_name in tags:
                    return [trait_name]

        trait_lower = trait_name.lower()
        fuzzy_map = {
            'anxious': ['anxious_response', 'needs_calm'],
            'confident': ['high_confidence', 'capable'],
            'organized': ['organized', 'structured'],
            'flexible': ['flexible', 'adaptive'],
            'creative': ['creative', 'intuitive_learner'],
            'systematic': ['systematic', 'detail_oriented'],
            'motivated': ['intrinsic_driven', 'learning_oriented'],
            'resilient': ['bounces_back', 'strong_resilience'],
        }
        for key, mapped in fuzzy_map.items():
            if key in trait_lower:
                return mapped
        return ['needs_support']

    def get_dominant_traits_tags(
        self,
        personality_vector: Optional[Dict[str, float]],
        top_n: int = 3,
    ) -> List[str]:
        """Return tags for the most dominant personality dimensions."""
        if not personality_vector:
            return []

        scores = {
            dimension: abs(value - 0.5)
            for dimension, value in personality_vector.items()
        }
        top_dimensions = sorted(
            scores.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_n]

        dominant_tags: List[str] = []
        for dimension, _ in top_dimensions:
            value = personality_vector.get(dimension, 0.5)
            if value < 0.33:
                tier = 'low'
            elif value < 0.67:
                tier = 'medium'
            else:
                tier = 'high'
            dominant_tags.extend(
                self.TRAIT_TO_TAG_MAPPING.get(dimension, {}).get(tier, [])
            )

        return list(dict.fromkeys(dominant_tags))


personality_mapper = PersonalityMapper()

