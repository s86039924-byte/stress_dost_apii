"""
PERSONALITY ASSESSMENT SYSTEM v2.1 (10 Question Adaptive Version)
Continuous 8-Dimensional Personality Vector Scoring
For JEE/NEET Student Personalization

This module uses a compact 10-question personality test with weighted
coverage across eight dimensions to generate a high-resolution
personality fingerprint for each student.
"""

import json
import os
import random
from typing import List, Dict, Tuple
from datetime import datetime
import statistics


class PersonalityAssessor:
    """Analyze adaptive personality assessments with weighted dimensions"""

    def __init__(
        self,
        questions_file_path: str = 'personality_assessment_questions.txt',
        question_limit: int = 10
    ):
        """
        Initialize assessor with questions dataset
        
        Args:
            questions_file_path: Path to personality_assessment_30q.txt
        """
        data = self._load_question_file(questions_file_path)
        all_questions = data.get('questions', [])
        random.shuffle(all_questions)
        self.assessment_metadata = data.get('assessment_metadata', {})
        self.dimension_metadata = data.get('personality_dimensions', {})

        inferred_dimensions = self._extract_dimensions(data)
        self.personality_dimensions = inferred_dimensions

        max_questions = len(all_questions)
        limit = question_limit if question_limit else max_questions
        self.total_questions = min(max(1, limit), max_questions)
        self.questions = all_questions[:self.total_questions]

        self.question_dimension_weights = self._build_question_dimension_weights(self.questions)
        self.dimension_expected_counts = self._compute_expected_counts(self.question_dimension_weights)
    
    def _load_question_file(self, file_path: str) -> Dict:
        """Load assessment JSON with metadata"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print(f"Error: {file_path} not found")
            return {'questions': []}
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in {file_path}")
            return {'questions': []}

    def _extract_dimensions(self, data: Dict) -> List[str]:
        """Derive unique dimensions from metadata/options"""
        if 'personality_dimensions' in data and data['personality_dimensions']:
            return list(data['personality_dimensions'].keys())

        dimensions = set()
        for question in data.get('questions', []):
            for option in question.get('options', []):
                dimensions.update(option.get('scores', {}).keys())
        return sorted(dimensions)

    def _build_question_dimension_weights(self, questions: List[Dict]) -> Dict[int, Dict[str, float]]:
        mapping: Dict[int, Dict[str, float]] = {}
        for question in questions:
            q_id = question.get('id')
            dims = set()
            for option in question.get('options', []):
                dims.update(option.get('scores', {}).keys())
            dims = {d for d in dims if d in self.personality_dimensions}
            if not q_id or not dims:
                continue
            weight = 1.0 / len(dims)
            mapping[q_id] = {dimension: weight for dimension in dims}
        return mapping

    def _compute_expected_counts(self, mapping: Dict[int, Dict[str, float]]) -> Dict[str, int]:
        counts = {dim: 0 for dim in self.personality_dimensions}
        for weights in mapping.values():
            for dimension in weights.keys():
                counts[dimension] += 1
        return counts
    
    def get_all_questions(self) -> List[Dict]:
        """Return sanitized questions for frontend display"""
        questions_for_display = []
        
        for q in self.questions:
            question_obj = {
                'id': q['id'],
                'category': q['category'],
                'question': q['question'],
                'options': [
                    {'text': opt['text']}
                    for opt in q['options']
                ]
            }
            questions_for_display.append(question_obj)
        
        return questions_for_display
    
    def analyze_responses(self, responses: List[Dict]) -> Dict:
        """Analyze 10 responses and return 8D vector with weight verification"""

        expected_count = self.total_questions
        if len(responses) != expected_count:
            raise ValueError(f"Expected {expected_count} responses, got {len(responses)}")

        dimension_scores: Dict[str, Dict[str, float]] = {
            dim: {'weighted_sum': 0.0, 'total_weight': 0.0}
            for dim in self.personality_dimensions
        }
        extracted_traits = []

        for response in responses:
            q_id = response.get('question_id')
            opt_idx = response.get('option_index')

            question = next((q for q in self.questions if q['id'] == q_id), None)
            if not question or opt_idx is None:
                continue

            options = question.get('options', [])
            if opt_idx < 0 or opt_idx >= len(options):
                continue

            option = options[opt_idx]
            scores = option.get('scores', {})
            traits = option.get('traits', [])

            dimension_weights = self.question_dimension_weights.get(q_id, {})
            for dimension, weight in dimension_weights.items():
                raw_score = scores.get(dimension, 0.5)
                dimension_scores[dimension]['weighted_sum'] += raw_score * weight
                dimension_scores[dimension]['total_weight'] += weight

            extracted_traits.extend(traits)

        personality_vector = {}
        for dimension in self.personality_dimensions:
            totals = dimension_scores[dimension]
            if totals['total_weight'] > 0:
                avg_score = totals['weighted_sum'] / totals['total_weight']
                personality_vector[dimension] = round(avg_score, 2)
            else:
                personality_vector[dimension] = 0.5

        trait_frequency = {}
        for trait in extracted_traits:
            trait_frequency[trait] = trait_frequency.get(trait, 0) + 1

        top_traits = [t for t, count in trait_frequency.items() if count >= 2]
        summary = self._generate_summary(personality_vector)
        recommendations = self._generate_recommendations(personality_vector)
        weight_check = self._verify_weights(responses)

        return {
            'personality_vector': personality_vector,
            'traits': top_traits,
            'trait_details': trait_frequency,
            'summary': summary,
            'recommendations': recommendations,
            'weight_check': weight_check,
            'valid': weight_check.get('all_dimensions_covered', False),
            'timestamp': datetime.now().isoformat()
        }

    def _verify_weights(self, responses: List[Dict]) -> Dict:
        """Report coverage for each dimension based on answered questions"""

        coverage = {dim: 0 for dim in self.personality_dimensions}

        for response in responses:
            q_id = response.get('question_id')
            dimension_weights = self.question_dimension_weights.get(q_id, {})
            for dimension in dimension_weights.keys():
                if dimension in coverage:
                    coverage[dimension] += 1

        report = {
            dim: f"{coverage.get(dim, 0)}/{self.dimension_expected_counts.get(dim, 0)}"
            for dim in coverage
        }

        all_dimensions_covered = all(
            coverage.get(dim, 0) > 0 or self.dimension_expected_counts.get(dim, 0) == 0
            for dim in self.personality_dimensions
        )

        return {
            'coverage': coverage,
            'expected': self.dimension_expected_counts,
            'report': report,
            'all_dimensions_covered': all_dimensions_covered,
            'total_questions_processed': len(responses)
        }
    
    def _generate_summary(self, personality_vector: Dict) -> str:
        """Generate human-readable personality summary"""
        
        stress = personality_vector['stress_sensitivity']
        analytical = personality_vector['analytical_thinking']
        social = personality_vector['social_preference']
        motivation = personality_vector['intrinsic_motivation']
        resilience = personality_vector['resilience']
        confidence = personality_vector['self_confidence']
        planning = personality_vector['planning_tendency']
        feedback = personality_vector['openness_to_feedback']
        
        # Classify each dimension
        classifications = []
        
        # Stress sensitivity
        if stress < 0.35:
            classifications.append("calm under pressure")
        elif stress > 0.65:
            classifications.append("highly anxiety-prone")
        else:
            classifications.append("moderate stress response")
        
        # Analytical thinking
        if analytical > 0.75:
            classifications.append("strong analytical thinker")
        elif analytical < 0.35:
            classifications.append("intuitive/creative learner")
        else:
            classifications.append("balanced thinker")
        
        # Social preference
        if social > 0.70:
            classifications.append("extrovert, collaborative")
        elif social < 0.35:
            classifications.append("introvert, independent")
        else:
            classifications.append("ambivert, flexible socially")
        
        # Motivation
        if motivation > 0.70:
            classifications.append("intrinsically motivated (mastery-driven)")
        elif motivation < 0.35:
            classifications.append("extrinsically motivated (reward-driven)")
        else:
            classifications.append("mixed motivation")
        
        # Resilience
        if resilience > 0.70:
            classifications.append("highly resilient, bounces back quickly")
        elif resilience < 0.35:
            classifications.append("struggles after setbacks")
        else:
            classifications.append("moderate resilience")
        
        # Confidence
        if confidence > 0.70:
            classifications.append("high self-confidence")
        elif confidence < 0.35:
            classifications.append("low self-confidence, self-doubting")
        else:
            classifications.append("moderate confidence")
        
        # Planning
        if planning > 0.70:
            classifications.append("organized, planned approach")
        elif planning < 0.35:
            classifications.append("spontaneous, adaptive learner")
        else:
            classifications.append("balanced planning style")
        
        # Feedback openness
        if feedback > 0.70:
            classifications.append("highly open to feedback")
        elif feedback < 0.35:
            classifications.append("defensive, closed to criticism")
        else:
            classifications.append("moderately receptive to feedback")
        
        # Build summary
        summary = "Personality Profile: " + ", ".join(classifications) + "."
        return summary
    
    def _generate_recommendations(self, personality_vector: Dict) -> Dict:
        """Generate personalized recommendations based on personality vector"""
        
        stress = personality_vector['stress_sensitivity']
        analytical = personality_vector['analytical_thinking']
        social = personality_vector['social_preference']
        motivation = personality_vector['intrinsic_motivation']
        resilience = personality_vector['resilience']
        confidence = personality_vector['self_confidence']
        planning = personality_vector['planning_tendency']
        feedback = personality_vector['openness_to_feedback']
        
        recommendations = {}
        
        # QUESTION DIFFICULTY RECOMMENDATION
        if stress >= 0.70 or resilience <= 0.35:
            recommended_difficulty = 0.30
            difficulty_reason = "High stress/low resilience - use easier questions to stabilize confidence"
        elif stress >= 0.55:
            recommended_difficulty = 0.40
            difficulty_reason = "Moderate stress - keep difficulty gentle but progressive"
        elif stress <= 0.35 and confidence >= 0.55:
            recommended_difficulty = 0.70
            difficulty_reason = "Low stress and decent confidence - push difficulty upward"
        elif confidence >= 0.80 and analytical >= 0.70:
            recommended_difficulty = 0.85
            difficulty_reason = "Very confident + analytical - unlock toughest problems"
        elif planning <= 0.30:
            recommended_difficulty = 0.50
            difficulty_reason = "Spontaneous planner - keep moderate difficulty for focus"
        else:
            recommended_difficulty = 0.55
            difficulty_reason = "Balanced profile - steady medium difficulty"
        
        recommendations['question_difficulty'] = {
            'value': recommended_difficulty,
            'reason': difficulty_reason
        }
        
        # QUESTION POOL RECOMMENDATION
        if stress >= 0.70:
            question_pool = 'acadza_easy'
            pool_reason = "High anxiety - start with comforting known questions"
        elif analytical >= 0.70 and confidence >= 0.60:
            question_pool = 'acadza_challenging'  # Hard Acadza questions
            pool_reason = "Strong analytical skills - focus on challenging problems"
        elif analytical < 0.40:
            question_pool = 'mixed_with_visual'  # Visual + practical
            pool_reason = "Intuitive learner - use visual explanations and applications"
        elif planning < 0.35 and stress < 0.40:
            question_pool = 'generated_mixed'  # Generated questions for variety
            pool_reason = "Spontaneous learner - varied generated questions"
        else:
            question_pool = 'mixed_adaptive'  # Mix of both
            pool_reason = "Balanced profile - mix of Acadza and generated questions"
        
        recommendations['question_pool'] = {
            'value': question_pool,
            'reason': pool_reason
        }
        
        # TRIGGER FREQUENCY RECOMMENDATION
        if stress >= 0.75:
            trigger_frequency = 4
            freq_reason = "High stress - nudge often with calming triggers"
        elif resilience <= 0.35:
            trigger_frequency = 5
            freq_reason = "Low resilience - regular encouragement between questions"
        elif planning < 0.30:
            trigger_frequency = 3  # Every 3 questions (high pressure)
            freq_reason = "Spontaneous, procrastinator - frequent triggers for urgency"
        elif confidence > 0.80 and analytical > 0.80:
            trigger_frequency = 10  # Every 10 questions (minimal)
            freq_reason = "High confidence - let them flow, minimal interruptions"
        elif social > 0.75:
            trigger_frequency = 4  # Every 4 questions (regular feedback)
            freq_reason = "Social, feedback-seeker - regular social validation triggers"
        else:
            trigger_frequency = 6  # Every 6 questions (standard)
            freq_reason = "Standard trigger frequency for balanced approach"
        
        recommendations['trigger_frequency'] = {
            'value': trigger_frequency,
            'reason': freq_reason
        }
        
        # TRIGGER TYPE RECOMMENDATION
        trigger_types = []
        if stress > 0.70:
            trigger_types.append('motivational')  # Calming triggers
            trigger_types.append('confidence_building')
        elif planning < 0.35:
            trigger_types.append('urgency')  # Deadline-based triggers
            trigger_types.append('pressure')
        elif social > 0.75:
            trigger_types.append('social_validation')  # Peer comparison
            trigger_types.append('recognition')
        else:
            trigger_types.append('analytical_challenge')  # Intellectual
            trigger_types.append('mastery_focus')
        
        recommendations['trigger_types'] = trigger_types
        
        # LEARNING STYLE RECOMMENDATION
        learning_style = []
        if analytical > 0.75:
            learning_style.append("Deep conceptual understanding")
        else:
            learning_style.append("Practical application + step-by-step")
        
        if social > 0.60:
            learning_style.append("Collaborative study recommended")
        else:
            learning_style.append("Solo study optimal")
        
        if planning > 0.70:
            learning_style.append("Structure your study schedule")
        else:
            learning_style.append("Flexible, adaptive study timing")
        
        recommendations['learning_style'] = learning_style
        
        # STRESS MANAGEMENT RECOMMENDATION
        if stress > 0.70:
            stress_mgmt = [
                "Take frequent breaks (5 min per hour)",
                "Use calming techniques (breathing exercises)",
                "Start with easier questions to build momentum",
                "Practice mindfulness or meditation"
            ]
        elif stress < 0.35:
            stress_mgmt = [
                "Push yourself with challenging problems",
                "Use pressure and competition as motivation"
            ]
        else:
            stress_mgmt = [
                "Maintain steady, consistent pace",
                "Balance study with breaks"
            ]
        
        recommendations['stress_management'] = stress_mgmt
        
        # FEEDBACK HANDLING RECOMMENDATION
        if feedback < 0.40:
            feedback_advice = "Work on accepting criticism - try reframing feedback as data, not judgment"
        else:
            feedback_advice = "Use feedback actively - implement suggestions immediately"
        
        recommendations['feedback_handling'] = feedback_advice
        
        return recommendations


class ContinuousPersonalitySelector:
    """
    Selects questions based on continuous personality vector
    Instead of categorical profiles
    """
    
    def __init__(self):
        self.personality_dimensions = [
            'stress_sensitivity',
            'analytical_thinking',
            'social_preference',
            'intrinsic_motivation',
            'resilience',
            'self_confidence',
            'planning_tendency',
            'openness_to_feedback'
        ]
    
    def get_personality_profile_name(self, personality_vector: Dict) -> str:
        """
        Get closest profile name for display (optional)
        But actual selection uses continuous vector, not this name
        """
        stress = personality_vector['stress_sensitivity']
        analytical = personality_vector['analytical_thinking']
        confidence = personality_vector['self_confidence']
        resilience = personality_vector['resilience']
        planning = personality_vector['planning_tendency']
        motivation = personality_vector['intrinsic_motivation']
        
        # Multi-factor classification (still using continuous, not hard-coded)
        if stress > 0.70 and confidence < 0.50:
            return "High Stress Sensitive"
        elif analytical > 0.80 and planning > 0.75 and stress < 0.35:
            return "Problem Solver"
        elif planning < 0.30 and motivation < 0.40:
            return "Procrastinator"
        elif stress < 0.40 and resilience > 0.80 and motivation > 0.75:
            return "Balanced Learner"
        else:
            return "Adaptive Learner"
    
    def calculate_question_affinity(
        self,
        personality_vector: Dict,
        question_properties: Dict
    ) -> float:
        """
        Calculate how well a question matches this personality
        
        Args:
            personality_vector: 8D continuous personality scores
            question_properties: Question properties like:
                {
                    'difficulty': 0.7,
                    'analytical_load': 0.8,
                    'social_context': 0.2,
                    'time_pressure': 0.3,
                    'creativity_required': 0.5,
                    'memorization_required': 0.2,
                    'practical_application': 0.7,
                    'deep_concept': 0.8
                }
        
        Returns:
            Affinity score 0.0-1.0 (higher = better match)
        """
        
        affinity = 0.0
        weights = {}
        
        # Match stress tolerance to time pressure
        stress = personality_vector['stress_sensitivity']
        time_pressure = question_properties.get('time_pressure', 0.5)
        stress_match = 1.0 - abs(stress - time_pressure)  # Inverse - low stress high time OK
        weights['stress_time'] = 0.15
        affinity += stress_match * weights['stress_time']
        
        # Match analytical ability to question demands
        analytical = personality_vector['analytical_thinking']
        analytical_load = question_properties.get('analytical_load', 0.5)
        analytical_match = 1.0 - abs(analytical - analytical_load)
        weights['analytical'] = 0.20
        affinity += analytical_match * weights['analytical']
        
        # Match social preference to question context
        social = personality_vector['social_preference']
        social_context = question_properties.get('social_context', 0.5)
        social_match = 1.0 - abs(social - social_context)
        weights['social'] = 0.10
        affinity += social_match * weights['social']
        
        # Match motivation to question type
        motivation = personality_vector['intrinsic_motivation']
        practical = question_properties.get('practical_application', 0.5)
        deep = question_properties.get('deep_concept', 0.5)
        # High intrinsic = prefer deep concept; Low intrinsic = prefer practical
        motivation_match = abs(motivation - deep) if motivation > 0.6 else abs((1-motivation) - practical)
        motivation_match = max(0, 1.0 - motivation_match)
        weights['motivation'] = 0.15
        affinity += motivation_match * weights['motivation']
        
        # Match resilience to difficulty
        resilience = personality_vector['resilience']
        difficulty = question_properties.get('difficulty', 0.5)
        # High resilience can handle high difficulty
        resilience_match = 1.0 - abs(resilience - difficulty)
        weights['resilience'] = 0.15
        affinity += resilience_match * weights['resilience']
        
        # Match confidence to expected success
        confidence = personality_vector['self_confidence']
        memorization = question_properties.get('memorization_required', 0.5)
        # High confidence prefers challenging, low confidence prefers memorization
        confidence_match = 1.0 - abs((1-confidence) - memorization)
        weights['confidence'] = 0.10
        affinity += confidence_match * weights['confidence']
        
        # Match planning tendency to structure
        planning = personality_vector['planning_tendency']
        structure = question_properties.get('structure_level', 0.5)
        planning_match = 1.0 - abs(planning - structure)
        weights['planning'] = 0.10
        affinity += planning_match * weights['planning']
        
        # Normalize to 0-1
        total_weight = sum(weights.values())
        if total_weight > 0:
            affinity = affinity / total_weight
        
        return round(affinity, 3)


# ============================================================================
# INTEGRATION EXAMPLES
# ============================================================================

def integrate_with_session(session_obj, personality_assessment_data):
    """
    Integrate continuous personality assessment with existing UserSession
    
    Args:
        session_obj: UserSession instance from app.py
        personality_assessment_data: Result from PersonalityAssessor.analyze_responses()
    """
    
    # Store personality vector (continuous, 8-dimensional)
    session_obj.personality_assessment = {
        'vector': personality_assessment_data['personality_vector'],
        'traits': personality_assessment_data['traits'],
        'recommendations': personality_assessment_data['recommendations'],
        'timestamp': personality_assessment_data['timestamp']
    }
    
    # Apply recommendations to session
    recommendations = personality_assessment_data['recommendations']
    
    session_obj.current_difficulty = recommendations['question_difficulty']['value']
    session_obj.recommended_trigger_frequency = recommendations['trigger_frequency']['value']
    session_obj.question_pool = recommendations['question_pool']['value']
    session_obj.trigger_types = recommendations['trigger_types']
    
    # Store original personality vector for adaptive updates
    session_obj.personality_vector = personality_assessment_data['personality_vector'].copy()
    
    # Mark assessment complete
    session_obj.personality_completed = True
    
    print(f"✓ Personality assessment integrated")
    print(f"  Difficulty: {session_obj.current_difficulty}")
    print(f"  Trigger frequency: Every {session_obj.recommended_trigger_frequency} questions")
    print(f"  Question pool: {session_obj.question_pool}")


def adaptive_update_personality(
    session_obj,
    recent_performance: List[Dict]
):
    """
    Update personality vector based on actual performance
    Called after every 5 questions
    
    Args:
        session_obj: UserSession instance
        recent_performance: Last 5 performance records
            [
                {'question_id': 1, 'correct': True, 'time_taken': 120},
                ...
            ]
    """
    
    if len(recent_performance) < 5:
        return
    
    # Calculate performance metrics
    accuracy = sum(1 for p in recent_performance if p.get('correct')) / 5
    avg_time = statistics.mean([p.get('time_taken', 0) for p in recent_performance])
    
    # Update personality vector based on performance
    personality_vec = session_obj.personality_vector.copy()
    
    if accuracy > 0.90:  # Questions too easy
        # Student is more capable than thought
        personality_vec['analytical_thinking'] = min(1.0, personality_vec['analytical_thinking'] * 1.1)
        personality_vec['self_confidence'] = min(1.0, personality_vec['self_confidence'] * 1.05)
        personality_vec['stress_sensitivity'] = max(0.0, personality_vec['stress_sensitivity'] * 0.95)
        session_obj.current_difficulty = min(0.95, session_obj.current_difficulty + 0.1)
        
        update_reason = "INCREASE: Student excelling, questions too easy"
    
    elif accuracy < 0.50:  # Questions too hard
        # Student more stressed/less capable than thought
        personality_vec['stress_sensitivity'] = min(1.0, personality_vec['stress_sensitivity'] * 1.1)
        personality_vec['self_confidence'] = max(0.0, personality_vec['self_confidence'] * 0.95)
        personality_vec['resilience'] = max(0.0, personality_vec['resilience'] * 0.95)
        session_obj.current_difficulty = max(0.15, session_obj.current_difficulty - 0.1)
        
        update_reason = "DECREASE: Student struggling, questions too hard"
    
    else:
        update_reason = "NO CHANGE: Performance matches expectation"
        return  # No update needed
    
    # Apply updated vector
    session_obj.personality_vector = personality_vec
    
    # Log update event
    print(f"✓ Personality Update (After Q{session_obj.current_question_index}):")
    print(f"  Reason: {update_reason}")
    print(f"  New difficulty: {session_obj.current_difficulty}")
    print(f"  Performance: {accuracy*100:.0f}% accuracy")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: Initialize and get questions
    print("=" * 70)
    print("PERSONALITY ASSESSMENT SYSTEM v2.0 - USAGE EXAMPLES")
    print("=" * 70)
    
    assessor = PersonalityAssessor('personality_assessment_30q.txt')
    
    print("\n1. GETTING QUESTIONS FOR FRONTEND:")
    print("-" * 70)
    questions = assessor.get_all_questions()
    print(f"Total questions: {len(questions)}")
    print(f"Sample question {questions[0]['id']}: {questions[0]['question'][:60]}...")
    print(f"Options: {len(questions[0]['options'])}")
    
    # Example 2: Analyze sample responses
    print("\n2. ANALYZING RESPONSES - SAMPLE DATA:")
    print("-" * 70)
    
    sample_responses = [
        {'question_id': i+1, 'option_index': (i % 4)} for i in range(30)
    ]
    
    result = assessor.analyze_responses(sample_responses)
    
    print(f"Personality Vector (8 dimensions):")
    for dim, score in result['personality_vector'].items():
        bar = "█" * int(score * 20)
        print(f"  {dim:25s}: {score:.2f} {bar}")
    
    print(f"\nExtracted Traits: {', '.join(result['traits'][:5])}")
    print(f"\nSummary: {result['summary']}")
    
    # Example 3: Get recommendations
    print("\n3. RECOMMENDATIONS:")
    print("-" * 70)
    recs = result['recommendations']
    
    print(f"Question Difficulty: {recs['question_difficulty']['value']}")
    print(f"  Reason: {recs['question_difficulty']['reason']}")
    
    print(f"\nQuestion Pool: {recs['question_pool']['value']}")
    print(f"  Reason: {recs['question_pool']['reason']}")
    
    print(f"\nTrigger Frequency: Every {recs['trigger_frequency']['value']} questions")
    print(f"  Reason: {recs['trigger_frequency']['reason']}")
    
    print(f"\nTrigger Types: {', '.join(recs['trigger_types'])}")
    
    print(f"\nLearning Style: {', '.join(recs['learning_style'])}")
    
    print(f"\nStress Management:")
    for tip in recs['stress_management']:
        print(f"  • {tip}")
    
    # Example 4: Continuous personality selector
    print("\n4. CONTINUOUS PERSONALITY MATCHING:")
    print("-" * 70)
    
    selector = ContinuousPersonalitySelector()
    profile_name = selector.get_personality_profile_name(result['personality_vector'])
    print(f"Closest Profile Name: {profile_name} (for display only)")
    
    # Example question with properties
    question_props = {
        'difficulty': 0.65,
        'analytical_load': 0.80,
        'social_context': 0.20,
        'time_pressure': 0.40,
        'creativity_required': 0.50,
        'memorization_required': 0.30,
        'practical_application': 0.60,
        'deep_concept': 0.75
    }
    
    affinity = selector.calculate_question_affinity(
        result['personality_vector'],
        question_props
    )
    
    print(f"Question Affinity Score: {affinity:.3f} (0.0-1.0)")
    print(f"Interpretation: {'Perfect match' if affinity > 0.8 else 'Good match' if affinity > 0.6 else 'Moderate match' if affinity > 0.4 else 'Poor match'}")
    
    print("\n" + "=" * 70)
    print("✓ All examples completed successfully!")
    print("=" * 70)
