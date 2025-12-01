"""
Stress Dost - Stress Management Feature for JEE/NEET Preparation
Flask Backend with Real-time WebSocket, Groq Integration, Acadza Questions, and Google Sheets Logging
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import json
import random
import time
from datetime import datetime
import os
import re
import logging
from dotenv import load_dotenv
import httpx
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from groq import Groq

from personality_mapper import personality_mapper
from popup_selector import PopupSelector
from session_manager import SessionManager
from groq_generator import PersonalizedGroqGenerator

# ============================================================================
# LOAD ENV & CREATE FLASK APP FIRST
# ============================================================================

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'stress-dost-secret-2025')
socketio = SocketIO(app, cors_allowed_origins="*")
logger = logging.getLogger(__name__)

# ============================================================================
# IMPORT QUESTION SERVICE AFTER FLASK APP IS CREATED
# ============================================================================

from question_service import init_question_service, QuestionFormatter, acadza_fetcher

# ============================================================================
# IMPORT PERSONALITY ASSESSMENT MODULES
# ============================================================================

from personality_assessor import (
    PersonalityAssessor,
    ContinuousPersonalitySelector,
    integrate_with_session,
    adaptive_update_personality
)

personality_assessor = PersonalityAssessor(
    'personality_assessment_questions.txt',
    question_limit=10
)
personality_selector = ContinuousPersonalitySelector()

# Initialize question service with the Flask app
init_question_service(app)

# ============================================================================
# IMPORT METER CALCULATION MODULES
# ============================================================================

from meter_calculation_v2 import (
    StudentCalibration,
    TriggerResponse,
    MeterState,
    MeterCalculator,
    DifficultyAdjuster,
    ChatGPTContextBuilder
)

# ============================================================================
# CONFIGURATION
# ============================================================================

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
CHATGPT_TIMEOUT = 5  # seconds
METER_THRESHOLD = 0.8
DIFFICULTY_INCREMENT = 0.1

# Initialize Groq client
groq_client = None
groq_http_client = None

if GROQ_API_KEY:
    try:
        groq_http_client = httpx.Client()
        groq_client = Groq(api_key=GROQ_API_KEY, http_client=groq_http_client)
        print("✓ Groq client initialized (streaming mode)")
    except Exception as e:
        print(f"⚠ Failed to initialize Groq client: {e}")
        groq_client = None
else:
    groq_client = None

personalized_groq_generator = PersonalizedGroqGenerator(GROQ_API_KEY, GROQ_MODEL) if GROQ_API_KEY else None

# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'credentials.json')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Stress_Dost_Data')

# Load triggers dataset
try:
    with open('stress_dost_triggers.txt', 'r') as f:
        TRIGGERS_DATASET = json.load(f)
    print("✓ Triggers dataset loaded")
except Exception as e:
    print(f"⚠ Failed to load triggers dataset: {e}")
    TRIGGERS_DATASET = {}


def _preprocess_triggers(dataset):
    processed = {}
    if not isinstance(dataset, dict):
        return processed
    for category, items in dataset.items():
        processed[category] = []
        if isinstance(items, dict):
            iterator = items.items()
        else:
            iterator = enumerate(items)
        for key, data in iterator:
            if not isinstance(data, dict):
                continue
            popup = data.copy()
            popup['id'] = key
            raw_tags = popup.get('personality_tags', []) or popup.get('tags', [])
            canonical_tags = []
            for tag in raw_tags:
                canonical_tags.extend(personality_mapper.map_trait_name_to_tags(tag))
            tags = list(dict.fromkeys(canonical_tags)) if canonical_tags else raw_tags

            if len(tags) < 2:
                base_tags = personality_mapper.CATEGORY_TAG_ENRICHMENT.get(
                    category,
                    {}
                ).get('base_tags', [])
                for base_tag in base_tags:
                    if base_tag not in tags:
                        tags.append(base_tag)
                    if len(tags) >= 2:
                        break

            if len(tags) < 2:
                tags.extend(['supportive', 'encouragement'])
                tags = list(dict.fromkeys(tags))

            popup['tags'] = tags

            if len(tags) < 2:
                logger.warning("Popup %s still lacks rich tags after enrichment", key)

            processed[category].append(popup)
    return processed


PROCESSED_TRIGGERS = _preprocess_triggers(TRIGGERS_DATASET)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

# In-memory storage
user_sessions = {}

class UserSession:
    def __init__(self, user_id, session_id):
        self.user_id = user_id
        self.session_id = session_id
        self.start_time = datetime.now()
        self.calibration = StudentCalibration(
            baseline_reaction_time=float(os.getenv('BASELINE_REACTION_TIME', 3.0)),
            accuracy_baseline=float(os.getenv('ACCURACY_BASELINE', 0.7)),
            anxiety_level=os.getenv('BASELINE_ANXIETY_LEVEL', 'moderate'),
            processing_speed=os.getenv('PROCESSING_SPEED', 'normal')
        )
        self.meter_state = MeterState()
        self.meter_calculator = MeterCalculator(self.calibration)
        self.difficulty_adjuster = DifficultyAdjuster()
        self.chatgpt_context_builder = ChatGPTContextBuilder(self.meter_calculator)
        self.current_question_index = 0
        self.total_questions = 0
        self.question_start_time = None
        self.responses = []
        self.triggered_sentences = []
        self.current_difficulty = 1.0
        self.loaded_questions = []  # NEW: Store questions loaded from Acadza
        self.personality_assessment = None
        self.personality_completed = False
        self.personality_responses = []
        self.question_pool = 'mixed'
        self.recommended_trigger_frequency = 6
        self.personality_vector = None
        self.trigger_types = []
        self.session_manager = SessionManager(user_id)
        self.popup_selector = PopupSelector(session_id)
        self.current_traits = []
        self.popup_counter = 0
        self.trigger_source_counts = {
            'chatgpt': 0,
            'dataset': 0
        }
        self.test_category = 'thoughts'

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'fear_meter': round(self.meter_state.fear_meter, 3),
            'thought_meter': round(self.meter_state.thought_meter, 3),
            'frustration_meter': round(self.meter_state.frustration_meter, 3),
            'current_question': self.current_question_index,
            'total_questions': self.total_questions,
            'timestamp': self.start_time.isoformat(),
            'difficulty': self.current_difficulty,
            'personality_vector': self.personality_vector,
            'question_pool': self.question_pool,
            'trigger_frequency': self.recommended_trigger_frequency,
            'current_traits': self.current_traits,
            'personality_completed': self.personality_completed,
            'trigger_source_counts': self.trigger_source_counts,
            'popup_counter': self.popup_counter
        }

# ============================================================================
# GOOGLE SHEETS INTEGRATION
# ============================================================================

class GoogleSheetsLogger:
    def __init__(self, credentials_path, sheet_id, sheet_name):
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.worksheet = None
        self.setup_connection()

    def setup_connection(self):
        """Initialize Google Sheets connection"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path, scope
            )
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open_by_key(self.sheet_id)
            self.worksheet = spreadsheet.worksheet(self.sheet_name)
            print("✓ Google Sheets connected successfully")
        except Exception as e:
            print(f"⚠ Google Sheets connection failed: {e}")
            print("  Continuing in demo mode (data will be stored in memory only)")

    def log_response(self, user_id, session_id, question_index, trigger_data, response_data):
        """Log user response to Google Sheets"""
        if not self.worksheet:
            return False
        try:
            trigger_text = trigger_data.get('text', '')
            trigger_options = trigger_data.get('options')
            if trigger_options:
                options_str = ' | Options: ' + ' / '.join([str(opt) for opt in trigger_options])
                trigger_text = f"{trigger_text}{options_str}"

            row = [
                datetime.now().isoformat(),
                user_id,
                session_id,
                question_index,
                trigger_text,
                trigger_data.get('type', ''),
                response_data.get('selected_option', ''),
                response_data.get('time_taken', 0),
                response_data.get('answer_correct', False),
                response_data.get('fear_meter', 0),
                response_data.get('thought_meter', 0),
                response_data.get('frustration_meter', 0),
            ]
            self.worksheet.append_row(row)
            return True
        except Exception as e:
            print(f"⚠ Error logging to Google Sheets: {e}")
            return False

# Initialize Google Sheets logger (optional)
sheets_logger = None
if GOOGLE_SHEET_ID:
    try:
        sheets_logger = GoogleSheetsLogger(
            GOOGLE_SHEETS_CREDENTIALS,
            GOOGLE_SHEET_ID,
            GOOGLE_SHEET_NAME
        )
    except Exception as e:
        print(f"Google Sheets logging disabled: {e}")

# ============================================================================
# PERSONALITY ASSESSMENT ROUTES
# ============================================================================

@app.route('/api/personality/questions', methods=['GET'])
@app.route('/api/module/personality/questions', methods=['GET'])
def get_personality_questions():
    """Return personality assessment questions (30Q)"""
    questions = personality_assessor.get_all_questions()
    return jsonify({
        'status': 'success',
        'questions': questions,
        'total': len(questions),
        'estimated_time_minutes': 4
    })


@app.route('/api/personality/submit', methods=['POST'])
@app.route('/api/module/personality/submit', methods=['POST'])
def submit_personality_assessment():
    """Process submitted personality responses and store on the session"""
    data = request.json or {}
    session_id = data.get('session_id')
    responses = data.get('responses', [])

    session = user_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Invalid session'}), 404

    if not responses:
        return jsonify({'error': 'No responses provided'}), 400

    try:
        result = personality_assessor.analyze_responses(responses)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to analyze assessment: {e}'}), 500

    integrate_with_session(session, result)
    session.personality_responses = responses

    if session.session_manager and result.get('personality_vector'):
        session.session_manager.load_initial_personality(result['personality_vector'])
        state_snapshot = session.session_manager.get_session_state()
        session.personality_vector = state_snapshot.get('current_personality_vector')
        session.current_traits = state_snapshot.get('current_traits', [])

    recommendations = result.get('recommendations', {})

    return jsonify({
        'status': 'success',
        'personality_vector': result.get('personality_vector'),
        'summary': result.get('summary'),
        'traits': result.get('traits', []),
        'recommendations': recommendations,
        'weight_check': result.get('weight_check'),
        'valid': result.get('valid'),
        'question_pool': recommendations.get('question_pool', {}).get('value') if recommendations else session.question_pool,
        'difficulty': recommendations.get('question_difficulty', {}).get('value') if recommendations else session.current_difficulty,
        'trigger_frequency': recommendations.get('trigger_frequency', {}).get('value') if recommendations else session.recommended_trigger_frequency
    })

# ============================================================================
# GROQ (LLM) INTEGRATION
# ============================================================================

def get_chatgpt_trigger(session, label, force_option_based=False):
    """Generate Groq popup using enriched personality context."""
    if not personalized_groq_generator:
        return None

    personality_vector = session.personality_vector or {}
    if session.session_manager and not personality_vector:
        personality_vector = session.session_manager.current_personality_vector
    personality_vector = personality_vector or {}

    tags = personality_mapper.get_tags_from_personality(personality_vector, label)
    session_state = session.session_manager.get_session_state() if session.session_manager else {}
    student_state = {
        'personality_vector': personality_vector,
        'current_traits': session.current_traits or session_state.get('current_traits', []),
        'recent_accuracy': session_state.get('recent_accuracy')
    }

    accuracy_pct = session_state.get('recent_accuracy')
    accuracy_pct = round(accuracy_pct * 100, 1) if isinstance(accuracy_pct, (int, float)) else 'unknown'
    meter_context = {
        'accuracy': accuracy_pct,
        'trend': session.meter_state.get_severity_level(),
        'confidence': 'high' if personality_vector.get('self_confidence', 0.5) > 0.7 else 'medium'
    }

    try:
        popup = personalized_groq_generator.generate_popup(
            student_state,
            tags,
            label,
            meter_context,
            force_option_based=force_option_based
        )
        if popup:
            popup.setdefault('options', [])
            return popup
        return None
    except Exception as e:
        print(f"⚠ Groq API error: {e}")
        return None

# ============================================================================
# TRIGGER SELECTION LOGIC
# ============================================================================

def _determine_trigger_source_order(session, label):
    """Return ordered list of trigger sources to enforce a 50/50 split."""
    ai_available = personalized_groq_generator is not None
    dataset_available = bool(PROCESSED_TRIGGERS.get(label))
    if not ai_available and not dataset_available:
        return []

    counts = getattr(session, 'trigger_source_counts', {})
    ai_count = counts.get('chatgpt', 0)
    dataset_count = counts.get('dataset', 0)
    total = ai_count + dataset_count

    if ai_available and dataset_available:
        if total == 0:
            preferred = 'chatgpt'
        else:
            ai_ratio = ai_count / total if total else 0
            if ai_ratio < 0.5:
                preferred = 'chatgpt'
            elif ai_ratio > 0.5:
                preferred = 'dataset'
            else:
                preferred = random.choice(['chatgpt', 'dataset'])
        secondary = 'dataset' if preferred == 'chatgpt' else 'chatgpt'
        return [preferred, secondary]

    if ai_available:
        return ['chatgpt']
    return ['dataset']


def _select_dataset_trigger(session, label, needs_option_based):
    """Select a dataset trigger honoring option requirement and history."""
    popups = PROCESSED_TRIGGERS.get(label, [])
    if not popups:
        return None

    required_type = 'option_based' if needs_option_based else None
    if session.popup_selector:
        candidate = session.popup_selector.select_popup(
            session.personality_vector or (
                session.session_manager.current_personality_vector if session.session_manager else {}
            ),
            label,
            PROCESSED_TRIGGERS,
            required_type=required_type
        )
        if candidate and candidate.get('text') not in session.triggered_sentences:
            return candidate

    filtered = [
        popup for popup in popups
        if popup.get('text') not in session.triggered_sentences and (
            not needs_option_based or popup.get('type') == 'option_based'
        )
    ]
    return random.choice(filtered) if filtered else None


def _fallback_dataset_trigger(session, label):
    """Final fallback to any dataset trigger regardless of history."""
    popups = PROCESSED_TRIGGERS.get(label, [])
    if not popups:
        return None

    unused = [popup for popup in popups if popup.get('text') not in session.triggered_sentences]
    pool = unused if unused else popups
    return random.choice(pool) if pool else None


def _record_trigger_delivery(session, trigger_payload, next_count, source):
    """Update session bookkeeping when a trigger is delivered."""
    session.triggered_sentences.append(trigger_payload.get('text', ''))
    session.popup_counter = next_count
    counts = getattr(session, 'trigger_source_counts', None)
    if counts is None:
        counts = {'chatgpt': 0, 'dataset': 0}
        session.trigger_source_counts = counts
    counts[source] = counts.get(source, 0) + 1


def get_next_trigger(session, label):
    """
    Select next trigger using personality-aware weighting and Groq generation.
    """
    next_count = session.popup_counter + 1
    needs_option_based = (next_count % 2 == 0)

    def apply_difficulty(trigger_payload):
        """Return a copy of trigger payload with difficulty applied"""
        if not trigger_payload:
            return None
        scaled = json.loads(json.dumps(trigger_payload))
        value = scaled.get('value', 0.5)
        scaled['value'] = round(value * session.current_difficulty, 3)
        return scaled

    source_order = _determine_trigger_source_order(session, label)
    if not source_order:
        return None, 'none'

    requirement_order = [needs_option_based]
    if needs_option_based:
        requirement_order.append(False)

    for require_options in requirement_order:
        for source in source_order:
            trigger = None
            if source == 'chatgpt':
                trigger = get_chatgpt_trigger(
                    session,
                    label,
                    force_option_based=require_options
                )
            else:
                trigger = _select_dataset_trigger(session, label, require_options)

            if trigger:
                scaled_trigger = apply_difficulty(trigger)
                _record_trigger_delivery(session, trigger, next_count, source)
                return scaled_trigger, source

    fallback_trigger = _fallback_dataset_trigger(session, label)
    if fallback_trigger:
        scaled_trigger = apply_difficulty(fallback_trigger)
        _record_trigger_delivery(session, fallback_trigger, next_count, 'dataset')
        return scaled_trigger, 'dataset'

    return None, 'none'

# ============================================================================
# ROUTES
# ============================================================================

def _create_new_session(user_id, total_questions=5, test_category='thoughts'):
    """Create and register a new user session for the module layer."""
    if not user_id:
        raise ValueError('user_id is required to start a session')

    base_id = f"{user_id}_{int(time.time())}"
    suffix = random.randint(1000, 9999)
    session_id = f"{base_id}_{suffix}"
    # Avoid collisions when user restarts quickly
    while session_id in user_sessions:
        suffix = random.randint(1000, 9999)
        session_id = f"{base_id}_{suffix}"

    session = UserSession(user_id, session_id)
    session.total_questions = total_questions
    session.test_category = test_category or 'thoughts'
    user_sessions[session_id] = session
    return session

@app.route('/')
def index():
    """Serve main test interface"""
    return render_template('index.html')


@app.route('/api/session/<session_id>', methods=['GET'])
@app.route('/api/module/session/<session_id>', methods=['GET'])
def get_session_snapshot(session_id):
    """Return current session state for external apps."""
    session = user_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Invalid session'}), 404

    snapshot = session.to_dict()
    snapshot['meters'] = {
        'fear': session.meter_state.fear_meter,
        'thoughts': session.meter_state.thought_meter,
        'frustration': session.meter_state.frustration_meter
    }
    snapshot['triggers_served'] = len(session.responses)
    return jsonify({'status': 'success', 'session': snapshot})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get frontend configuration"""
    return jsonify({
        'chatgpt_timeout': CHATGPT_TIMEOUT,
        'meter_threshold': METER_THRESHOLD,
        'difficulty_increment': DIFFICULTY_INCREMENT,
        'version': '2.0.0',
        'features': {
            'personality_assessment': True,
            'questions_api': True,
            'chatgpt_integration': True,
            'google_sheets_logging': True
        }
    })

@app.route('/api/start-session', methods=['POST'])
@app.route('/api/module/session', methods=['POST'])
def start_session():
    """Initialize a test session"""
    data = request.json or {}
    user_id = data.get('user_id')
    total_questions = data.get('total_questions', 5)
    test_category = data.get('category', 'thoughts')
    include_questions = data.get('include_personality_questions', False)

    try:
        session = _create_new_session(user_id, total_questions, test_category)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    response_payload = {
        'session_id': session.session_id,
        'user_id': user_id,
        'category': test_category,
        'status': 'started',
        'message': 'Session initialized',
        'total_questions': total_questions,
        'next_step': 'personality_assessment',
        'session': session.to_dict()
    }

    if include_questions:
        assessment_questions = personality_assessor.get_all_questions()
        response_payload['personality_assessment'] = {
            'questions': assessment_questions,
            'total': len(assessment_questions),
            'estimated_time_minutes': 4
        }

    return jsonify(response_payload)

# ============================================================================
# NEW: QUESTION LOADING ROUTES (Acadza Integration)
# ============================================================================

@app.route('/api/fetch-test-questions', methods=['POST'])
def fetch_test_questions():
    """
    Fetch and format 20 questions for current session
    Called when test starts
    """
    try:
        data = request.json
        session_id = data.get('session_id')
        num_questions = data.get('num_questions', 20)

        session = user_sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Invalid session'}), 404

        if not session.personality_completed:
            return jsonify({'error': 'Personality assessment required first'}), 400

        # Get random question IDs (Acadza dataset not personalized)
        from question_service import question_loader
        question_ids = question_loader.get_random_ids(count=num_questions)

        # Fetch from Acadza API
        raw_questions = acadza_fetcher.fetch_multiple(question_ids)

        # Format for frontend
        formatted_questions = [
            QuestionFormatter.format_question(q, idx)
            for idx, q in enumerate(raw_questions)
        ]

        # Store in session for reference
        session.loaded_questions = formatted_questions
        session.total_questions = len(formatted_questions)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'questions': formatted_questions,
            'total_questions': len(formatted_questions),
            'question_pool': session.question_pool,
            'personality_vector': session.personality_vector,
            'message': f'Loaded {len(formatted_questions)} questions'
        })

    except Exception as e:
        import logging
        logging.error(f"Error fetching test questions: {e}")
        return jsonify({
            'error': str(e),
            'status': 'failed'
        }), 500

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    """
    Submit answer to a question
    Updated to work with Acadza question format
    """
    try:
        data = request.json
        session_id = data.get('session_id')
        question_id = data.get('question_id')
        selected_answer = data.get('selected_answer')
        time_taken = data.get('time_taken', 0)

        session = user_sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Invalid session'}), 404

        # Check if answer is correct
        question = next(
            (q for q in session.loaded_questions if q['question_id'] == question_id),
            None
        )

        if not question:
            return jsonify({'error': 'Question not found in session'}), 404

        # Determine correctness based on question type
        is_correct = False
        if question['question_type'] == 'scq':
            correct_answer = question.get('correct_answer', 'A')
            is_correct = selected_answer == correct_answer
        elif question['question_type'] == 'mcq':
            correct_answers = question.get('correct_answers', [])
            is_correct = selected_answer in correct_answers

        return jsonify({
            'status': 'success',
            'is_correct': is_correct,
            'correct_answer': question.get('correct_answer'),
            'time_taken': time_taken,
            'message': 'Answer recorded'
        })

    except Exception as e:
        import logging
        logging.error(f"Error submitting answer: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-question-by-index', methods=['POST'])
def get_question_by_index():
    """Get a specific question by its index in the test"""
    try:
        data = request.json
        session_id = data.get('session_id')
        question_index = data.get('question_index', 0)

        session = user_sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Invalid session'}), 404

        if not session.loaded_questions:
            return jsonify({'error': 'Questions not loaded'}), 400

        if question_index >= len(session.loaded_questions):
            return jsonify({'error': 'Question index out of range'}), 400

        question = session.loaded_questions[question_index]

        return jsonify({
            'status': 'success',
            'question': question,
            'question_number': question_index + 1,
            'total_questions': len(session.loaded_questions)
        })

    except Exception as e:
        import logging
        logging.error(f"Error getting question: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# EXISTING ROUTES (Trigger & Meter Management)
# ============================================================================

@app.route('/api/get-trigger', methods=['POST'])
@app.route('/api/module/trigger', methods=['POST'])
def get_trigger():
    """Get next trigger for current question"""
    data = request.json
    session_id = data.get('session_id')
    question_index = data.get('question_index', 0)
    label = data.get('label', 'thoughts')

    session = user_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Invalid session'}), 404

    if not session.personality_completed:
        return jsonify({
            'error': 'Personality assessment not completed',
            'status': 'pending_personality'
        }), 400

    session.current_question_index = question_index
    session.question_start_time = time.time()

    trigger, source = get_next_trigger(session, label)

    if not trigger:
        return jsonify({
            'trigger': None,
            'status': 'no_trigger_available'
        })

    return jsonify({
        'trigger': trigger,
        'source': source,
        'question_index': question_index,
        'session_id': session_id,
        'status': 'trigger_ready',
        'session': session.to_dict()
    })

@app.route('/api/submit-response', methods=['POST'])
@app.route('/api/module/trigger/response', methods=['POST'])
def submit_response():
    """Process user response to trigger"""
    data = request.json or {}
    session_id = data.get('session_id')
    trigger_data = data.get('trigger')
    response_data = data.get('response')

    session = user_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Invalid session'}), 404

    if not session.personality_completed:
        return jsonify({
            'error': 'Personality assessment not completed',
            'status': 'pending_personality'
        }), 400

    time_taken = response_data.get('time_taken', 0)
    answer_correct = response_data.get('answer_correct', False)
    selected_option = response_data.get('selected_option')
    trigger_type = trigger_data.get('type', 'sarcasm')
    trigger_value = trigger_data.get('value', 0.5)
    label = data.get('label', 'thoughts')
    trigger_text = trigger_data.get('text', '')

    question_time = response_data.get('question_time')
    if question_time is None and session.question_start_time:
        question_time = time.time() - session.question_start_time
    if question_time is None:
        question_time = max(time_taken, 0)

    repeat_count = session.meter_calculator.trigger_history.get(trigger_text, 0)

    trigger_response = TriggerResponse(
        trigger_text=trigger_text,
        trigger_type=trigger_type,
        category=label,
        trigger_value=trigger_value,
        time_taken=time_taken,
        selected_option=selected_option,
        main_question_correct=answer_correct,
        main_question_time=question_time,
        timestamp=datetime.now(),
        repeat_count=repeat_count
    )

    new_state, analysis = session.meter_calculator.process_trigger_response(
        trigger_response,
        session.meter_state
    )

    session.meter_state = new_state
    session.meter_calculator.response_history.append(trigger_response)

    session.difficulty_adjuster.add_performance(answer_correct, question_time)
    session.current_difficulty = session.difficulty_adjuster.get_difficulty_adjustment()

    session.responses.append({
        'question_index': session.current_question_index,
        'trigger_text': trigger_data.get('text', ''),
        'trigger_type': trigger_type,
        'selected_option': selected_option,
        'time_taken': time_taken,
        'answer_correct': answer_correct,
        'meter_analysis': analysis,
        'label': label,
        'timestamp': datetime.now().isoformat()
    })

    if sheets_logger:
        sheet_payload = dict(response_data)
        sheet_payload.update({
            'fear_meter': session.meter_state.fear_meter,
            'thought_meter': session.meter_state.thought_meter,
            'frustration_meter': session.meter_state.frustration_meter
        })
        sheets_logger.log_response(
            session.user_id,
            session_id,
            session.current_question_index,
            trigger_data,
            sheet_payload
        )

    if session.session_manager and session.personality_vector:
        session.session_manager.update_personality_from_performance({
            'correct': answer_correct,
            'response_time': question_time,
            'category': label
        })
        state_snapshot = session.session_manager.get_session_state()
        session.personality_vector = state_snapshot.get('current_personality_vector', session.personality_vector)
        session.current_traits = state_snapshot.get('current_traits', session.current_traits)

    return jsonify({
        'status': 'response_recorded',
        'meters': {
            'fear': session.meter_state.fear_meter,
            'thoughts': session.meter_state.thought_meter,
            'frustration': session.meter_state.frustration_meter
        },
        'current_difficulty': session.current_difficulty,
        'threshold_reached': max(
            session.meter_state.fear_meter,
            session.meter_state.thought_meter,
            session.meter_state.frustration_meter
        ) >= METER_THRESHOLD
    })

@app.route('/api/end-session', methods=['POST'])
@app.route('/api/module/session/end', methods=['POST'])
def end_session():
    """Finalize session and return results"""
    data = request.json
    session_id = data.get('session_id')

    session = user_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Invalid session'}), 404

    report = {
        'session_id': session_id,
        'user_id': session.user_id,
        'personality_vector': session.personality_vector,
        'duration_seconds': (datetime.now() - session.start_time).total_seconds(),
        'final_meters': {
            'fear': round(session.meter_state.fear_meter, 3),
            'thoughts': round(session.meter_state.thought_meter, 3),
            'frustration': round(session.meter_state.frustration_meter, 3),
            'average': round((session.meter_state.fear_meter + session.meter_state.thought_meter + session.meter_state.frustration_meter) / 3, 3)
        },
        'questions_attempted': session.current_question_index,
        'triggers_shown': len(session.responses),
        'final_difficulty': round(session.current_difficulty, 2),
        'responses': session.responses
    }

    del user_sessions[session_id]

    return jsonify(report)

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0.0',
        'active_sessions': len(user_sessions),
        'personality_assessment': 'active',
        'chatgpt_configured': bool(GROQ_API_KEY),
        'ai_provider': 'groq' if groq_client else 'none',
        'sheets_configured': sheets_logger is not None,
        'questions_api': 'active'
    })

# ============================================================================
# WEBSOCKET EVENTS (Real-time updates)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connection_response', {'data': 'Connected to Stress Dost server v2.0'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('meter_update')
def handle_meter_update(data):
    """Broadcast meter updates to all connected clients"""
    emit('meter_update', data, broadcast=True)

# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════╗
║         STRESS DOST v2.0 - Production Ready              ║
║  ✓ Groq AI Integration                                   ║
║  ✓ Acadza Question API Integration                       ║
║  ✓ Real-time WebSocket Updates                           ║
║  ✓ Google Sheets Logging                                 ║
║  ✓ Research-backed Meter Calculation                     ║
╚═══════════════════════════════════════════════════════════╝
    """)

    render_port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    socketio.run(
        app,
        debug=debug_mode,
        host='0.0.0.0',
        port=render_port,
        allow_unsafe_werkzeug=True  # Render runs behind its own proxy
    )
