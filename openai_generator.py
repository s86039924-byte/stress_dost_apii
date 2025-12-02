"""Groq prompt builder that injects personality context."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from groq import Groq

from personality_mapper import personality_mapper


class PersonalizedGroqGenerator:
    """Generate popup payloads that respect the student's personality."""

    def __init__(self, api_key: Optional[str], model: str = "mixtral-8x7b-32768"):
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=api_key) if api_key else None

    def generate_popup(
        self,
        student_state: Dict,
        selected_tags: List[str],
        category: str,
        meter_context: Optional[Dict] = None,
        force_option_based: bool = False,
    ) -> Optional[Dict]:
        """Call Groq with enriched prompt and return parsed popup dict."""
        if not self.client:
            return None

        personality_vector = student_state.get('personality_vector', {})
        traits = student_state.get('current_traits', [])
        profile_text = self._build_personality_profile(personality_vector, traits)
        prompt = self._build_prompt(
            profile_text,
            selected_tags,
            category,
            meter_context or {},
            force_option_based,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            max_tokens=400,
        )

        content = response.choices[0].message.content if response.choices else ''
        popup = self._parse_response(content)
        if not popup:
            return None

        valid, reason = self.validate_generation(popup, selected_tags, category)
        if not valid:
            print(f"Groq validation failed: {reason}")
            return None
        return popup

    def _build_personality_profile(
        self,
        personality_vector: Dict[str, float],
        traits: List[str],
    ) -> str:
        lines: List[str] = []
        if traits:
            lines.append(f"Top dynamic traits: {', '.join(traits)}")

        stress = personality_vector.get('stress_sensitivity', 0.5)
        if stress > 0.7:
            lines.append("Student experiences high stress; use calm tone.")
        elif stress < 0.3:
            lines.append("Student is calm under pressure; can handle challenges.")

        analytical = personality_vector.get('analytical_thinking', 0.5)
        if analytical > 0.7:
            lines.append("Prefers logical explanations and clear reasoning.")
        elif analytical < 0.3:
            lines.append("Prefers metaphors and big-picture framing.")

        intrinsic = personality_vector.get('intrinsic_motivation', 0.5)
        if intrinsic > 0.7:
            lines.append("Motivated by mastery and growth.")
        else:
            lines.append("Motivated by outcomes, recognition, or rewards.")

        impulsivity = personality_vector.get('impulsivity', 0.5)
        if impulsivity > 0.7:
            lines.append("Tends to rush; remind them to slow down and reflect.")

        if personality_vector.get('distraction_resistance', 0.5) < 0.3:
            lines.append("Struggles with focus; offer concrete focus tips.")

        return "\n".join(lines) if lines else "Student has balanced traits."

    def _build_prompt(
        self,
        personality_profile: str,
        selected_tags: List[str],
        category: str,
        meter_context: Dict,
        force_option_based: bool,
    ) -> str:
        accuracy = meter_context.get('accuracy', 'unknown')
        trend = meter_context.get('trend', 'stable')
        confidence = meter_context.get('confidence', 'medium')

        keyword_line = (
            f"PERSONALIZATION KEYWORDS: {', '.join(selected_tags) if selected_tags else 'none'}"
        )

        instructions = f"""You create short popup messages for a stressed JEE/NEET student.

PERSONALITY PROFILE:
{personality_profile}

ACTIVE TAGS: {', '.join(selected_tags) if selected_tags else 'none'}
{keyword_line}

PERFORMANCE CONTEXT:
- Accuracy: {accuracy}
- Trend: {trend}
- Confidence: {confidence}

CATEGORY: {category}

Requirements:
1. Keep under 60 words.
2. Reflect the personality cues above.
3. Include actionable, specific guidance.
4. Tone must fit the CATEGORY.
5. Use Indian exam prep context when helpful.
6. Mention at least one word or phrase from PERSONALIZATION KEYWORDS.
7. If you choose "option_based", include THREE distinct, context-aware options that show different reactions.
8. Inject clever sarcasm or trigger-style urgency when category warrants it (thought/fear/frustration all allow light sarcasm if supportive).
9. Each response must use a fresh, specific example or scenario (no repeats).
10. Output must be valid minified JSON with keys: type, text, options, value.

Respond ONLY with JSON like:
{{
  "type": "motivation|sarcasm|option_based",
  "text": "Message here",
  "options": ["opt1","opt2","opt3"],
  "value": 0.4
}}

If type != "option_based", return an empty list for options."""

        if force_option_based:
            instructions += "\nThis popup MUST be type \"option_based\" with exactly three options."
        else:
            instructions += "\nChoose whichever type fits the student's current need."

        if category == 'thoughts':
            instructions += "\nFocus on reasoning help or reframing over panic."
        elif category == 'frustration':
            instructions += "\nAcknowledge their effort, then push toward solutions."
        elif category == 'fear':
            instructions += "\nBe reassuring and stabilize their anxiety."
        return instructions

    def _parse_response(self, content: str) -> Optional[Dict]:
        if not content:
            return None
        snippet = content.strip()
        if snippet.startswith('```'):
            snippet = snippet.strip('`')
        if snippet.lower().startswith('json'):
            snippet = snippet[4:].strip()

        start = snippet.find('{')
        end = snippet.rfind('}')
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(snippet[start:end + 1])
        except json.JSONDecodeError:
            return None

    def validate_generation(
        self,
        popup: Dict,
        selected_tags: List[str],
        category: str,
    ) -> Tuple[bool, str]:
        if not popup.get('text'):
            return False, "Missing text"
        if popup.get('type') not in {'motivation', 'sarcasm', 'option_based'}:
            return False, "Invalid type"
        if popup['type'] != 'option_based':
            popup['options'] = []
        if not isinstance(popup.get('value', 0.3), (int, float)):
            return False, "Missing value"

        keywords = set()
        for tag in selected_tags:
            keywords.update(tag.replace('_', ' ').split())
        if keywords:
            text_lower = popup['text'].lower()
            if not any(keyword in text_lower for keyword in keywords):
                return False, "Text ignores personality tags"
        popup['category'] = category
        return True, "ok"
