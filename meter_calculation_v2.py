# Stress Dost - Enhanced Calculation Logic Implementation
# Python code for research-backed weighting system

"""
IMPLEMENTATION GUIDE FOR ENHANCED METER CALCULATION
This module provides the core algorithms for psychologically-valid stress measurement
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class StudentCalibration:
    """Student's baseline characteristics for personalized assessment"""
    baseline_reaction_time: float  # Average time in seconds
    accuracy_baseline: float  # Accuracy on neutral questions (0-1)
    anxiety_level: str  # "low" | "moderate" | "high"
    processing_speed: str  # "fast" | "normal" | "slow"
    
    @property
    def time_thresholds(self) -> Dict[str, float]:
        """Personalized time thresholds based on baseline"""
        quick_multiplier = 0.7 if self.processing_speed == "fast" else (
            0.85 if self.processing_speed == "normal" else 1.0
        )
        slow_multiplier = 1.5 if self.processing_speed == "fast" else (
            1.3 if self.processing_speed == "normal" else 1.2
        )
        
        return {
            'quick': self.baseline_reaction_time * quick_multiplier,
            'moderate': self.baseline_reaction_time,
            'slow': self.baseline_reaction_time * slow_multiplier
        }

@dataclass
class TriggerResponse:
    """Record of student's response to a trigger"""
    trigger_text: str
    trigger_type: str  # "option_based" | "sarcasm" | "motivation"
    category: str  # "fear" | "thoughts" | "frustration"
    trigger_value: float  # Base impact (0-1)
    time_taken: float  # Seconds to respond
    selected_option: Optional[int]  # 0, 1, or 2 for option_based; None for sarcasm
    main_question_correct: bool
    main_question_time: float  # Time to answer main question
    timestamp: datetime
    repeat_count: int  # How many times this trigger shown before

@dataclass
class MeterState:
    """Current emotional state"""
    fear_meter: float = 0.0
    thought_meter: float = 0.0
    frustration_meter: float = 0.0
    
    def get_dominant_meter(self) -> Tuple[str, float]:
        """Get which meter is highest and its value"""
        meters = {
            'fear': self.fear_meter,
            'thoughts': self.thought_meter,
            'frustration': self.frustration_meter
        }
        return max(meters.items(), key=lambda x: x[1])
    
    def get_severity_level(self) -> str:
        """Classify overall stress level"""
        avg = (self.fear_meter + self.thought_meter + self.frustration_meter) / 3
        if avg < 0.3:
            return "low"
        elif avg < 0.6:
            return "moderate"
        else:
            return "high"

# ============================================================================
# CORE CALCULATION FUNCTIONS
# ============================================================================

class MeterCalculator:
    """
    Research-backed calculation engine for stress meters
    Implements cognitive load theory + STAI framework
    """
    
    # Constants based on research
    DECAY_FACTOR = 0.95  # 5% recovery per question
    MAX_METER = 1.0
    MIN_METER = 0.0
    SENSITIZATION_RATE = 0.1  # 10% increase per repeat
    HABITUATION_RATE = 0.1  # 10% decrease per repeat
    
    def __init__(self, calibration: StudentCalibration):
        self.calibration = calibration
        self.trigger_history: Dict[str, int] = {}  # Track repeats
        self.response_history: List[TriggerResponse] = []
    
    # ========== PART 1: TIME-BASED CATEGORIZATION ==========
    
    def categorize_response_time(self, time_taken: float) -> str:
        """Categorize response time as quick/moderate/slow"""
        thresholds = self.calibration.time_thresholds
        
        if time_taken <= thresholds['quick']:
            return 'quick'
        elif time_taken <= thresholds['slow']:
            return 'moderate'
        else:
            return 'slow'
    
    # ========== PART 2: BASE IMPACT CALCULATION ==========
    
    def calculate_base_impact(
        self,
        trigger_type: str,
        trigger_value: float,
        response_time_category: str,
        answer_correct: bool,
        selected_option: Optional[int] = None
    ) -> float:
        """
        Calculate base meter impact (before modifiers)
        Based on trigger type and response characteristics
        """
        
        if trigger_type == 'option_based':
            return self._calculate_option_based_impact(
                trigger_value,
                selected_option
            )
        elif trigger_type == 'sarcasm':
            return self._calculate_sarcasm_impact(
                trigger_value,
                response_time_category,
                answer_correct
            )
        elif trigger_type == 'motivation':
            return trigger_value  # Usually negative
        else:
            return 0.0
    
    def _calculate_option_based_impact(
        self,
        trigger_value: float,
        selected_option: int
    ) -> float:
        """
        Calculate impact for option-based triggers
        
        Option 0 (Negative): 0.9x → Catastrophizing, hopelessness
        Option 1 (Positive): 0.25x → Resilience, growth mindset
        Option 2 (Neutral): 0.5x → Balanced response
        """
        multipliers = {
            0: 0.90,  # Negative option - high impact
            1: 0.25,  # Positive option - low impact
            2: 0.50   # Neutral option - medium impact
        }
        
        multiplier = multipliers.get(selected_option, 0.5)
        return trigger_value * multiplier
    
    def _calculate_sarcasm_impact(
        self,
        trigger_value: float,
        response_time_category: str,
        answer_correct: bool
    ) -> float:
        """
        Calculate impact for sarcasm triggers (4 cases)
        Based on reaction time + answer correctness
        
        Case 1: Slow + Wrong → 1.0x (highest impact)
        Case 2: Slow + Correct → 0.6x (medium impact)
        Case 3: Quick + Correct → 0.1x (minimal impact)
        Case 4: Quick + Wrong → 0.35x (moderate impact)
        """
        
        if response_time_category == 'slow':
            if answer_correct:
                multiplier = 0.60  # Case 2: Slow but overcame it
            else:
                multiplier = 1.00  # Case 1: Slow and failed
        else:  # quick or moderate
            if answer_correct:
                multiplier = 0.10  # Case 3: Fast and correct (unaffected)
            else:
                multiplier = 0.35  # Case 4: Fast but wrong (careless)
        
        return trigger_value * multiplier
    
    # ========== PART 3: REPEAT MODIFIERS (Sensitization/Habituation) ==========
    
    def apply_repeat_modifier(
        self,
        trigger_text: str,
        base_impact: float,
        previous_response_was_negative: bool
    ) -> float:
        """
        Apply sensitization or habituation based on trigger history
        
        Sensitization (70% of students): Same trigger gets worse
        Habituation (20% of students): Familiar trigger becomes easier
        Volatility (10%): Random pattern
        """
        
        repeat_count = self.trigger_history.get(trigger_text, 0)
        
        if repeat_count == 0:
            return base_impact
        
        # Determine student type (simplified - could be more sophisticated)
        if previous_response_was_negative:
            # Sensitization: Rumination effect
            sensitization_factor = 1.0 + (self.SENSITIZATION_RATE * repeat_count)
            modified_impact = base_impact * sensitization_factor
            # Cap at 95% of max possible
            return min(modified_impact, base_impact * 0.95)
        else:
            # Habituation: Familiar with trigger, confidence increases
            habituation_factor = (1.0 - self.HABITUATION_RATE) ** repeat_count
            modified_impact = base_impact * habituation_factor
            # Floor at 10% of base
            return max(modified_impact, base_impact * 0.1)
    
    # ========== PART 4: PERFORMANCE CONTEXT MODIFIER ==========
    
    def apply_performance_context_modifier(
        self,
        base_impact: float,
        main_question_time: float,
        main_question_correct: bool
    ) -> float:
        """
        Adjust impact based on performance context
        
        If correct & fast: -15% (resilient, unaffected)
        If correct & slow: no change (affected but overcame)
        If wrong & fast: +10% (careless/reckless)
        If wrong & slow: +20% (completely overwhelmed)
        """
        
        # Determine time category for main question
        time_category = self.categorize_response_time(main_question_time)
        
        if main_question_correct and time_category == 'quick':
            # Resilient performance
            modifier = 0.85  # Reduce by 15%
        elif main_question_correct and time_category == 'moderate':
            modifier = 1.0   # No change
        elif main_question_correct and time_category == 'slow':
            modifier = 1.0   # Fighting through but managed
        elif not main_question_correct and time_category == 'quick':
            modifier = 1.10  # Increase by 10% (careless)
        elif not main_question_correct and time_category == 'moderate':
            modifier = 1.15  # Increase by 15%
        else:  # Wrong and slow
            modifier = 1.20  # Increase by 20% (completely overwhelmed)
        
        return base_impact * modifier
    
    # ========== PART 5: METER UPDATE CALCULATION ==========
    
    def calculate_meter_update(
        self,
        response: TriggerResponse
    ) -> Dict[str, float]:
        """
        Complete meter update calculation
        Returns dict with updates to each meter
        """
        
        # Step 1: Categorize response time
        response_time_category = self.categorize_response_time(response.time_taken)
        
        # Step 2: Calculate base impact
        base_impact = self.calculate_base_impact(
            response.trigger_type,
            response.trigger_value,
            response_time_category,
            response.main_question_correct,
            response.selected_option
        )
        
        # Step 3: Apply repeat modifiers
        previous_negative = response.selected_option == 0 if response.selected_option is not None else False
        base_impact = self.apply_repeat_modifier(
            response.trigger_text,
            base_impact,
            previous_negative
        )
        
        # Step 4: Apply performance context
        base_impact = self.apply_performance_context_modifier(
            base_impact,
            response.main_question_time,
            response.main_question_correct
        )
        
        # Step 5: Track this trigger
        self.trigger_history[response.trigger_text] = response.repeat_count + 1
        
        # Step 6: Build update dict (only target category gets update)
        updates = {
            'fear': 0.0,
            'thoughts': 0.0,
            'frustration': 0.0,
            'response_time_category': response_time_category,
            'base_impact_before_modifiers': response.trigger_value,
            'final_impact': base_impact
        }
        
        # Update only the target category
        if response.category == 'fear':
            updates['fear'] = base_impact
        elif response.category == 'thoughts':
            updates['thoughts'] = base_impact
        elif response.category == 'frustration':
            updates['frustration'] = base_impact
        
        return updates
    
    # ========== PART 6: APPLY METER UPDATES WITH DECAY ==========
    
    def apply_updates_to_meters(
        self,
        current_state: MeterState,
        updates: Dict[str, float]
    ) -> MeterState:
        """
        Apply calculated updates to meter state
        Also apply decay to other meters
        """
        
        # Extract update values
        fear_update = updates['fear']
        thoughts_update = updates['thoughts']
        frustration_update = updates['frustration']
        
        # Apply decay to all meters (natural recovery)
        new_state = MeterState(
            fear_meter=current_state.fear_meter * self.DECAY_FACTOR,
            thought_meter=current_state.thought_meter * self.DECAY_FACTOR,
            frustration_meter=current_state.frustration_meter * self.DECAY_FACTOR
        )
        
        # Add updates (clamped to 0-1 range)
        new_state.fear_meter = min(
            self.MAX_METER,
            max(self.MIN_METER, new_state.fear_meter + fear_update)
        )
        new_state.thought_meter = min(
            self.MAX_METER,
            max(self.MIN_METER, new_state.thought_meter + thoughts_update)
        )
        new_state.frustration_meter = min(
            self.MAX_METER,
            max(self.MIN_METER, new_state.frustration_meter + frustration_update)
        )
        
        return new_state
    
    # ========== PART 7: FULL PIPELINE ==========
    
    def process_trigger_response(
        self,
        response: TriggerResponse,
        current_state: MeterState
    ) -> Tuple[MeterState, Dict]:
        """
        Complete processing pipeline
        Input: Trigger response + current meter state
        Output: Updated meter state + detailed analysis
        """
        
        # Calculate updates
        updates = self.calculate_meter_update(response)
        
        # Apply to current state
        new_state = self.apply_updates_to_meters(current_state, updates)
        
        # Generate analysis
        analysis = {
            'response_time_category': updates['response_time_category'],
            'base_impact': updates['base_impact_before_modifiers'],
            'final_impact': updates['final_impact'],
            'meters_before': {
                'fear': round(current_state.fear_meter, 3),
                'thoughts': round(current_state.thought_meter, 3),
                'frustration': round(current_state.frustration_meter, 3)
            },
            'meters_after': {
                'fear': round(new_state.fear_meter, 3),
                'thoughts': round(new_state.thought_meter, 3),
                'frustration': round(new_state.frustration_meter, 3)
            },
            'dominant_stress_before': current_state.get_dominant_meter()[0],
            'dominant_stress_after': new_state.get_dominant_meter()[0],
            'severity_before': current_state.get_severity_level(),
            'severity_after': new_state.get_severity_level(),
            'trigger_repeat_count': self.trigger_history.get(response.trigger_text, 1)
        }
        
        return new_state, analysis

# ============================================================================
# DIFFICULTY ADJUSTMENT LOGIC
# ============================================================================

class DifficultyAdjuster:
    """Adjust trigger difficulty based on performance"""
    
    WINDOW_SIZE = 4  # Look at last 4 responses
    
    def __init__(self):
        self.performance_window: List[Tuple[bool, float]] = []
    
    def add_performance(self, correct: bool, time_taken: float):
        """Add response to performance window"""
        self.performance_window.append((correct, time_taken))
        if len(self.performance_window) > self.WINDOW_SIZE:
            self.performance_window.pop(0)
    
    def should_increase_difficulty(self) -> bool:
        """
        Increase difficulty if student is performing too well
        
        Criteria: 3-4 correct answers, avg time <3.5s
        """
        
        if len(self.performance_window) < 3:
            return False
        
        correct_count = sum(1 for c, _ in self.performance_window if c)
        avg_time = sum(t for _, t in self.performance_window) / len(self.performance_window)
        
        # 3-4 correct in last 4, AND fast processing
        if correct_count >= 3 and avg_time < 3.5:
            return True
        
        return False
    
    def should_decrease_difficulty(self) -> bool:
        """
        Decrease difficulty if student is struggling too much
        
        Criteria: 0-1 correct answers in window OR avg time >5s
        """
        
        if len(self.performance_window) < 2:
            return False
        
        correct_count = sum(1 for c, _ in self.performance_window if c)
        avg_time = sum(t for _, t in self.performance_window) / len(self.performance_window)
        
        # 0-1 correct, OR consistently slow
        if correct_count <= 1 or avg_time > 5.0:
            return True
        
        return False
    
    def get_difficulty_adjustment(self) -> float:
        """
        Return difficulty multiplier to apply to trigger values
        
        Returns:
            0.8 - decrease by 20%
            0.9 - decrease by 10%
            1.0 - no change
            1.1 - increase by 10%
            1.15 - increase by 15%
        """
        
        if self.should_increase_difficulty():
            correct_count = sum(1 for c, _ in self.performance_window if c)
            if correct_count == 4:
                return 1.15  # All correct, increase more
            else:
                return 1.10
        elif self.should_decrease_difficulty():
            correct_count = sum(1 for c, _ in self.performance_window if c)
            if correct_count == 0:
                return 0.80  # All wrong, decrease more
            else:
                return 0.90
        else:
            return 1.0  # Keep stable

# ============================================================================
# CHATGPT CONTEXT BUILDER
# ============================================================================

class ChatGPTContextBuilder:
    """Build context for ChatGPT trigger generation"""
    
    def __init__(self, calculator: MeterCalculator):
        self.calculator = calculator
    
    def build_context(
        self,
        current_state: MeterState,
        recent_responses: List[TriggerResponse],
        difficulty_adjustment: float
    ) -> Dict:
        """
        Build comprehensive context for ChatGPT
        """
        
        # Calculate recent performance
        recent_correct = sum(1 for r in recent_responses if r.main_question_correct)
        recent_accuracy = recent_correct / len(recent_responses) if recent_responses else 0.0
        avg_time = sum(r.main_question_time for r in recent_responses) / len(recent_responses) if recent_responses else 0.0
        
        # Get stress trend
        if len(recent_responses) >= 2:
            stress_trend = "increasing" if current_state.fear_meter > 0.6 else (
                "decreasing" if current_state.fear_meter < 0.3 else "stable"
            )
        else:
            stress_trend = "unknown"
        
        # Calculate next trigger intensity
        dominant_meter, dominant_value = current_state.get_dominant_meter()
        next_intensity = min(1.0, dominant_value * difficulty_adjustment)
        
        context = {
            "student_profile": {
                "baseline_anxiety": "moderate" if self.calculator.calibration.anxiety_level == "moderate" else (
                    "low" if self.calculator.calibration.anxiety_level == "low" else "high"
                ),
                "time_processing": self.calculator.calibration.processing_speed,
                "reaction_style": "resilient" if recent_accuracy > 0.7 else "struggling",
            },
            "current_emotional_state": {
                "fear_meter": round(current_state.fear_meter, 3),
                "thought_meter": round(current_state.thought_meter, 3),
                "frustration_meter": round(current_state.frustration_meter, 3),
                "dominant_stress": dominant_meter,
                "severity_level": current_state.get_severity_level(),
                "trend": stress_trend,
            },
            "recent_performance": {
                "last_answers_correct": [r.main_question_correct for r in recent_responses[-3:]],
                "accuracy": round(recent_accuracy, 2),
                "avg_response_time": round(avg_time, 2),
            },
            "trigger_history": {
                "triggers_shown": len(self.calculator.trigger_history),
                "most_effective_category": dominant_meter,
                "sensitization_pattern": "moderate",
            },
            "next_trigger_request": {
                "category": dominant_meter,
                "intensity": round(next_intensity, 2),
                "type": "option_based" if len(self.calculator.response_history) % 2 == 0 else "sarcasm",
                "avoid_repeats": list(self.calculator.trigger_history.keys())[-5:],  # Avoid last 5
            }
        }
        
        return context

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize
    calibration = StudentCalibration(
        baseline_reaction_time=3.0,
        accuracy_baseline=0.7,
        anxiety_level="moderate",
        processing_speed="normal"
    )
    
    calculator = MeterCalculator(calibration)
    current_meters = MeterState(fear_meter=0.0, thought_meter=0.0, frustration_meter=0.0)
    
    # Example response
    response = TriggerResponse(
        trigger_text="What if I fail?",
        trigger_type="sarcasm",
        category="fear",
        trigger_value=0.75,
        time_taken=2.8,
        selected_option=None,
        main_question_correct=True,
        main_question_time=3.2,
        timestamp=datetime.now(),
        repeat_count=1
    )
    
    # Process
    new_meters, analysis = calculator.process_trigger_response(response, current_meters)
    
    # Generate context for ChatGPT
    context_builder = ChatGPTContextBuilder(calculator)
    chatgpt_context = context_builder.build_context(new_meters, [response], 1.0)
    
    # Print results
    print("New Meter State:", new_meters.__dict__)
    print("Analysis:", analysis)
    print("ChatGPT Context:", chatgpt_context)
