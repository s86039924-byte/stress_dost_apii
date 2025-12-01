"""
Stress Dost - Acadza Question Integration Service
Fetches, formats, and serves questions from Acadza API to frontend
"""

from flask import Blueprint, jsonify, request
from flask_caching import Cache
import requests
import json
import csv
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
question_bp = Blueprint('questions', __name__, url_prefix='/api/questions')

# Cache configuration
cache = Cache(config={'CACHE_TYPE': 'simple'})

# ============================================================================
# CONSTANTS
# ============================================================================

ACADZA_API_URL = 'https://api.acadza.in/question/details'
QUESTIONS_CSV_PATH = './data/question_ids.csv'
CACHE_TIMEOUT = 3600  # 1 hour

# Acadza API headers
ACADZA_HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7',
    'Content-Type': 'application/json',
    'Origin': 'https://www.acadza.com',
    'Referer': 'https://www.acadza.com/',
    'Connection': 'keep-alive'
}

# ============================================================================
# QUESTION LOADER - CSV Management
# ============================================================================

class QuestionIDLoader:
    """Manages loading and random selection of question IDs from CSV"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.question_ids = []
        self.load_ids()
    
    def load_ids(self) -> None:
        """Load all question IDs from CSV"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.question_ids = [row['question_id'].strip() for row in reader]
            logger.info(f"✓ Loaded {len(self.question_ids)} question IDs from {self.csv_path}")
        except FileNotFoundError:
            logger.error(f"❌ CSV file not found: {self.csv_path}")
            self.question_ids = []
        except Exception as e:
            logger.error(f"❌ Error loading CSV: {e}")
            self.question_ids = []
    
    def get_random_ids(self, count: int = 20) -> List[str]:
        """Get N random question IDs"""
        if len(self.question_ids) < count:
            logger.warning(f"⚠ Only {len(self.question_ids)} IDs available, requested {count}")
            return self.question_ids
        return random.sample(self.question_ids, count)
    
    def get_all_ids(self) -> List[str]:
        """Get all question IDs"""
        return self.question_ids

# Initialize loader
question_loader = QuestionIDLoader(QUESTIONS_CSV_PATH)

# ============================================================================
# ACADZA API CLIENT
# ============================================================================

class AcadzaQuestionFetcher:
    """Handles communication with Acadza API"""
    
    def __init__(self, api_url: str, headers: Dict):
        self.api_url = api_url
        self.headers = headers
        self.request_timeout = 10  # seconds
    
    def fetch_question(self, question_id: str) -> Optional[Dict]:
        """
        Fetch single question from Acadza API
        
        Args:
            question_id: Acadza question ID
            
        Returns:
            Question data or None if error
        """
        try:
            payload = {}
            headers = self.headers.copy()
            headers['questionId'] = question_id
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Fetched question: {question_id}")
                return response.json()
            else:
                logger.warning(f"⚠ API returned {response.status_code} for {question_id}")
                return None
                
        except requests.Timeout:
            logger.error(f"❌ Timeout fetching question {question_id}")
            return None
        except requests.RequestException as e:
            logger.error(f"❌ Error fetching question {question_id}: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON response for question {question_id}")
            return None
    
    def fetch_multiple(self, question_ids: List[str]) -> List[Dict]:
        """
        Fetch multiple questions
        
        Args:
            question_ids: List of question IDs
            
        Returns:
            List of question data
        """
        questions = []
        for qid in question_ids:
            data = self.fetch_question(qid)
            if data:
                questions.append(data)
        
        logger.info(f"✓ Fetched {len(questions)}/{len(question_ids)} questions")
        return questions

# Initialize fetcher
acadza_fetcher = AcadzaQuestionFetcher(ACADZA_API_URL, ACADZA_HEADERS)

# ============================================================================
# QUESTION FORMATTER
# ============================================================================

class QuestionFormatter:
    """Formats raw Acadza question data into frontend-ready format"""
    
    @staticmethod
    def format_question(raw_data: Dict, question_index: int = 0) -> Dict:
        """
        Format raw Acadza question for frontend display
        
        Args:
            raw_data: Raw response from Acadza API
            question_index: Position in test (0-indexed)
            
        Returns:
            Formatted question data
        """
        
        question_type = raw_data.get('questionType', 'scq')
        
        # Route to appropriate formatter
        if question_type == 'scq':
            return QuestionFormatter._format_scq(raw_data, question_index)
        elif question_type == 'mcq':
            return QuestionFormatter._format_mcq(raw_data, question_index)
        elif question_type == 'integerQuestion':
            return QuestionFormatter._format_integer(raw_data, question_index)
        else:
            return QuestionFormatter._format_scq(raw_data, question_index)  # Default
    
    @staticmethod
    def _format_scq(raw_data: Dict, idx: int) -> Dict:
        """Format Single Correct Question (SCQ)"""
        scq_data = raw_data.get('scq', {})
        
        # Extract question HTML
        question_html = scq_data.get('question', '<p>Question not available</p>')
        
        # Extract answer options from HTML (parse A, B, C, D)
        options = QuestionFormatter._extract_options_from_html(question_html)
        
        # Get correct answer
        correct_answer = scq_data.get('answer', 'A')
        
        return {
            'question_id': raw_data.get('_id', 'unknown'),
            'question_index': idx + 1,
            'question_type': 'scq',
            'subject': raw_data.get('subject', 'Unknown'),
            'chapter': raw_data.get('chapter', 'Unknown'),
            'difficulty': raw_data.get('difficulty', 'Medium'),
            'level': raw_data.get('level', 'MEDIUM'),
            'question_html': question_html,
            'question_images': scq_data.get('quesImages', []),
            'options': options,
            'correct_answer': correct_answer,
            'solution_html': scq_data.get('solution', '<p>Solution not available</p>'),
            'solution_images': scq_data.get('solutionImages', []),
            'metadata': {
                'smart_trick': raw_data.get('smartTrick', False),
                'trap': raw_data.get('trap', False),
                'silly_mistake': raw_data.get('sillyMistake', False),
                'is_lengthy': raw_data.get('isLengthy', 0),
                'is_ncert': raw_data.get('isNCERT', False),
                'tag_subconcepts': QuestionFormatter._extract_subconcepts(raw_data)
            }
        }
    
    @staticmethod
    def _format_mcq(raw_data: Dict, idx: int) -> Dict:
        """Format Multiple Correct Question (MCQ)"""
        mcq_data = raw_data.get('mcq', {})
        question_html = raw_data.get('scq', {}).get('question', '<p>Question not available</p>')
        
        return {
            'question_id': raw_data.get('_id', 'unknown'),
            'question_index': idx + 1,
            'question_type': 'mcq',
            'subject': raw_data.get('subject', 'Unknown'),
            'chapter': raw_data.get('chapter', 'Unknown'),
            'difficulty': raw_data.get('difficulty', 'Medium'),
            'level': raw_data.get('level', 'MEDIUM'),
            'question_html': question_html,
            'question_images': mcq_data.get('quesImages', []),
            'correct_answers': mcq_data.get('answer', []),
            'solution_html': raw_data.get('scq', {}).get('solution', '<p>Solution not available</p>'),
            'solution_images': mcq_data.get('solutionImages', []),
            'metadata': {
                'smart_trick': raw_data.get('smartTrick', False),
                'trap': raw_data.get('trap', False),
            }
        }
    
    @staticmethod
    def _format_integer(raw_data: Dict, idx: int) -> Dict:
        """Format Integer Answer Question"""
        int_data = raw_data.get('integerQuestion', {})
        question_html = raw_data.get('scq', {}).get('question', '<p>Question not available</p>')
        
        return {
            'question_id': raw_data.get('_id', 'unknown'),
            'question_index': idx + 1,
            'question_type': 'integer',
            'subject': raw_data.get('subject', 'Unknown'),
            'chapter': raw_data.get('chapter', 'Unknown'),
            'difficulty': raw_data.get('difficulty', 'Medium'),
            'level': raw_data.get('level', 'MEDIUM'),
            'question_html': question_html,
            'question_images': int_data.get('quesImages', []),
            'solution_html': raw_data.get('scq', {}).get('solution', '<p>Solution not available</p>'),
            'solution_images': int_data.get('solutionImages', []),
            'metadata': {}
        }
    
    @staticmethod
    def _extract_options_from_html(html: str) -> List[Dict]:
        """
        Extract options (A, B, C, D) from HTML
        
        Note: This is a simplified extraction. May need adjustment based on actual HTML structure.
        """
        options = []
        
        # Look for option patterns (A), (B), (C), (D)
        import re
        pattern = r'\(([A-D])\)\s*(.+?)(?=\(|$)'
        
        matches = re.findall(pattern, html, re.DOTALL)
        for label, content in matches:
            # Clean up content
            clean_content = content.strip()
            # Remove HTML tags but keep math
            clean_content = re.sub(r'<[^>]+>', '', clean_content).strip()
            
            options.append({
                'label': label,
                'text': clean_content[:200]  # Truncate for preview
            })
        
        # If extraction failed, return default options
        if len(options) < 4:
            options = [
                {'label': 'A', 'text': 'Option A'},
                {'label': 'B', 'text': 'Option B'},
                {'label': 'C', 'text': 'Option C'},
                {'label': 'D', 'text': 'Option D'},
            ]
        
        return options
    
    @staticmethod
    def _extract_subconcepts(raw_data: Dict) -> List[str]:
        """Extract subconcepts from metadata"""
        subconcepts = []
        for tag in raw_data.get('tagSubConcept', []):
            if 'subConcept' in tag:
                subconcepts.append(tag['subConcept'])
        return subconcepts

# ============================================================================
# ROUTE HANDLERS
# ============================================================================

@question_bp.route('/load-test-questions', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUT)
def load_test_questions():
    """
    Load and format 20 random questions for a test
    
    Returns:
        {
            "status": "success",
            "questions": [...],
            "total_questions": 20,
            "timestamp": "ISO timestamp"
        }
    """
    try:
        # Get 20 random question IDs
        question_ids = question_loader.get_random_ids(count=20)
        
        if not question_ids:
            return jsonify({
                'status': 'error',
                'message': 'No question IDs available',
                'questions': []
            }), 400
        
        # Fetch questions from Acadza API
        raw_questions = acadza_fetcher.fetch_multiple(question_ids)
        
        # Format questions for frontend
        formatted_questions = [
            QuestionFormatter.format_question(q, idx)
            for idx, q in enumerate(raw_questions)
        ]
        
        return jsonify({
            'status': 'success',
            'questions': formatted_questions,
            'total_questions': len(formatted_questions),
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"❌ Error loading test questions: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'questions': []
        }), 500

@question_bp.route('/get-question/<question_id>', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUT, query_string=True)
def get_single_question(question_id: str):
    """
    Get a single question by ID
    
    Args:
        question_id: Acadza question ID
        
    Returns:
        Formatted question data
    """
    try:
        raw_question = acadza_fetcher.fetch_question(question_id)
        
        if not raw_question:
            return jsonify({
                'status': 'error',
                'message': f'Question {question_id} not found'
            }), 404
        
        formatted = QuestionFormatter.format_question(raw_question)
        
        return jsonify({
            'status': 'success',
            'question': formatted
        })
    
    except Exception as e:
        logger.error(f"❌ Error getting question {question_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@question_bp.route('/prefetch-batch', methods=['POST'])
def prefetch_batch():
    """
    Prefetch and format a batch of questions
    Useful for caching before test starts
    
    Request body:
        {
            "question_ids": ["id1", "id2", ...]
        }
    """
    try:
        data = request.json
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return jsonify({
                'status': 'error',
                'message': 'No question IDs provided'
            }), 400
        
        raw_questions = acadza_fetcher.fetch_multiple(question_ids)
        formatted_questions = [
            QuestionFormatter.format_question(q, idx)
            for idx, q in enumerate(raw_questions)
        ]
        
        return jsonify({
            'status': 'success',
            'questions': formatted_questions,
            'prefetched_count': len(formatted_questions)
        })
    
    except Exception as e:
        logger.error(f"❌ Error prefetching batch: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@question_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get stats about available questions"""
    return jsonify({
        'total_questions_available': len(question_loader.question_ids),
        'csv_path': QUESTIONS_CSV_PATH,
        'sample_ids': question_loader.get_random_ids(5)
    })

# ============================================================================
# CSV CREATION HELPER
# ============================================================================

def create_sample_csv(file_path: str, num_questions: int = 100):
    """
    Create a sample CSV file with question IDs for testing
    (You'll replace this with your actual question IDs)
    """
    import os
    
    # Create data directory if needed
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Sample Acadza question IDs (replace with your actual IDs)
    sample_ids = [
        '611798e8a43687635a0f69ee',  # Your example
        '611798e8a43687635a0f69ef',
        # ... add 98 more
    ]
    
    # If you don't have enough, generate pattern-based ones
    if len(sample_ids) < num_questions:
        base_id = '611798e8a43687635a0f69'
        for i in range(num_questions - len(sample_ids)):
            hex_suffix = format(ord('e') + (i % 26), 'x')
            sample_ids.append(f"{base_id}{hex_suffix}")
    
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['question_id'])  # Header
        for qid in sample_ids[:num_questions]:
            writer.writerow([qid])
    
    logger.info(f"✓ Created sample CSV with {num_questions} question IDs")

# ============================================================================
# INTEGRATION WITH MAIN APP
# ============================================================================

def init_question_service(app):
    """Initialize question service with Flask app"""
    app.register_blueprint(question_bp)
    cache.init_app(app)
    logger.info("✓ Question service initialized")
