# 🧠 Stress Dost - Psychological Stress Assessment Feature

## Overview

**Stress Dost** is an intelligent stress management system designed specifically for JEE/NEET students. It works by displaying psychological triggers during mock tests to assess how students handle emotional pressure, distraction, and stress.

### Why Stress Dost?

JEE/NEET success requires not just academic knowledge, but also:
- ✅ **Mental Resilience** - Handle pressure during exam
- ✅ **Emotional Regulation** - Manage anxiety and frustration
- ✅ **Distraction Management** - Stay focused under stress
- ✅ **Psychological Preparedness** - Know how you react under pressure

**Stress Dost measures all of these through scientifically-designed stress triggers.**

---

## 🎯 How It Works

### The 3-Meter System

During each test, Stress Dost tracks three stress dimensions:

#### 1. 😨 **Fear Meter**
- "What if I fail?"
- "What about my future?"
- Panic-based thoughts
- **Value Range:** 0.0 - 1.0

#### 2. 💭 **Thoughts Meter (Overthinking)**
- "I'm not smart enough"
- "My friends are doing better"
- Self-doubt and comparison
- **Value Range:** 0.0 - 1.0

#### 3. 😤 **Frustration Meter**
- "I've wasted time and money"
- "I keep making mistakes"
- Parental pressure and taunts
- **Value Range:** 0.0 - 1.0

### Trigger Types

#### Type 1: Option-Based Triggers
```
Question: "What if I can't solve this in the exam?"

Options:
[A] I will definitely fail (Negative)
[B] I might struggle but I'll try (Positive)
[C] I've solved harder questions (Confident)
```
**Effect:** Measures how student responds to negative self-talk

#### Type 2: Sarcasm Triggers (No Options)
```
Text: "Tick tock... time's running out and you're still stuck!"
```
**Action:** Student swipes away to continue

**Effect:** Measures distraction resilience and emotional numbness

#### Type 3: Motivation Triggers
```
Text: "You've prepared well for this. Trust your preparation!"
```
**Effect:** Reduces stress meters (negative values)

---

## 📊 Meter Calculation Logic

### For Option-Based Triggers

```
If student selects NEGATIVE option:
  meter_update = trigger_value × 0.9
  (High stress increase - they're demotivated)

If student selects POSITIVE option:
  meter_update = trigger_value × 0.3
  (Low stress increase - they're motivated)

If student selects NEUTRAL option:
  meter_update = trigger_value × 0.5
  (Medium stress increase - balanced)
```

### For Sarcasm Triggers (4 Cases)

```
Case 1: Took 3+ seconds + Wrong Answer
  → meter_update = trigger_value × 1.0
  → Highest impact (distraction affected performance)

Case 2: Took 3+ seconds + Correct Answer
  → meter_update = trigger_value × 0.6
  → Medium impact (student affected but overcame)

Case 3: Quick answer + Correct Answer
  → meter_update = trigger_value × 0.1
  → Minimal impact (trigger didn't distract)

Case 4: Quick answer + Wrong Answer
  → meter_update = trigger_value × 0.4
  → Low impact (carelessness or emotional numbness)
```

### For Motivation Triggers

```
meter_update = trigger_value  (usually -0.2 to -0.4)
→ Directly reduces appropriate stress meter
```

---

## 🤖 ChatGPT Integration

### Real-Time Personalization

Stress Dost uses ChatGPT to generate **personalized triggers** based on:
- Current meter values (fear, thoughts, frustration)
- Student's difficulty level
- Previously triggered sentences
- Student's emotional patterns

### Trigger Generation (50/50 Split)

```
50% of triggers = Pre-written from dataset
50% of triggers = ChatGPT-generated (personalized)
```

### ChatGPT Response Strategy

```
Request sent with context:
├── Current stress meters
├── Difficulty level
├── Category (thoughts/fear/frustration)
└── Previous triggers shown

ChatGPT generates JSON with:
├── type: option_based|sarcasm|motivation
├── text: Trigger sentence
├── options: [option1, option2, option3] (if option_based)
└── value: Stress increase value

Timeout: 5 seconds
Fallback: Use dataset trigger if ChatGPT slow
```

---

## 📱 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (index.html)                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Question   │    │   Trigger    │    │   Meters     │  │
│  │   Display    │    │   Popup      │    │   Display    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕ WebSocket
┌─────────────────────────────────────────────────────────────┐
│              BACKEND (app.py - Flask)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Session Management                                  │   │
│  │  ├── User authentication                             │   │
│  │  ├── Session creation & tracking                     │   │
│  │  └── Real-time meter updates                         │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Trigger Selection (50/50 Split)                     │   │
│  │  ├── Dataset triggers (pre-written)                  │   │
│  │  └── ChatGPT triggers (generated)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Meter Calculation                                   │   │
│  │  ├── Option-based calculation                        │   │
│  │  ├── Sarcasm 4-case logic                            │   │
│  │  └── Difficulty adjustment                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         ↕                          ↕                     ↕
    ┌────────────┐        ┌──────────────────┐    ┌──────────┐
    │ ChatGPT    │        │ Google Sheets    │    │ Question │
    │ API        │        │ (Data Logging)   │    │ Bank API │
    └────────────┘        └──────────────────┘    └──────────┘
```

---

## 🔄 Data Flow

### Session Start
```
1. Frontend: User clicks "Start Test"
2. Backend: Creates session, initializes meters to 0
3. Database: Logs session start
4. Frontend: Shows first question
```

### During Test (Per Question)
```
1. Question displayed
2. Trigger popup appears (either dataset or ChatGPT)
3. Timer starts tracking distraction time
4. Student responds to trigger (or dismisses)
5. Meter calculation happens
6. Database logs response
7. Next question loads
```

### Wrong Answer Trigger
```
1. Student selects wrong answer
2. Additional trigger appears
3. Same flow as normal question trigger
4. Difficulty adjusted if needed
```

### Session End
```
1. Student ends test
2. Final meters calculated
3. Comprehensive report generated
4. Data stored in Google Sheets
5. Results displayed to student
```

---

## 🔌 Module API for External Apps

Already have your own test UI? Use the module purely as a service layer with these endpoints (all prefixed with `/api/module`, mirrored under `/api` for backward compatibility):

1. **Start session** – `POST /api/module/session`
   ```json
   {
     "user_id": "student_42",
     "total_questions": 15,
     "include_personality_questions": true
   }
   ```
   Response → `{ session_id, session, next_step, personality_assessment? }`

2. **Render/submit personality test** – fetch questions via the start response or `GET /api/module/personality/questions`. Submit answers to `/api/module/personality/submit`. Until this step succeeds, trigger calls return `status: pending_personality`.

3. **Monitor session state** – `GET /api/module/session/<session_id>` returns meters, traits, trigger frequency, and live `trigger_source_counts` so you can display everything inside the host product.

4. **Request triggers** – `POST /api/module/trigger` with `{ session_id, question_index, label }`.
   Response includes:
   - `trigger`: popup payload (text/options/value)
   - `source`: `dataset` or `chatgpt`
   - `session`: snapshot (meters, difficulty, counts)

   The backend now enforces a session-level 50/50 split between Groq and the `stress_dost_triggers.txt` dataset. Counts in the snapshot confirm the balance.

5. **Submit trigger response** – `POST /api/module/trigger/response` with `{ session_id, trigger, response }` so Stress Dost can update timers, meters, and adaptive personality vectors.

6. **End session** – `POST /api/module/session/end` for the final report.

Use the standard `/api/health` endpoint to monitor the service. All responses are JSON, making the module easy to drop into any larger stack.

---

## 🚀 Render Auto Deploy

Deploying on Render now only needs the bundled Blueprint:

1. Install the Render CLI and log in (`npm i -g render-cli` then `render login`).
2. Run `render blueprint deploy render.yaml` from the repo root. The file defines a Python web service that installs requirements and starts `python app.py`, already wired for `PORT`/`FLASK_DEBUG`.
3. Set your secrets (e.g., `GROQ_API_KEY`, `SECRET_KEY`, `GOOGLE_SHEET_ID`) either via the CLI prompt or later in the Render dashboard. Values marked `sync: false` remain placeholder slots.
4. After the build finishes, hit `<render-url>/api/health` to verify the service.

Render auto-deploys on every git push unless you toggle `autoDeploy` in `render.yaml` to false.

---

## 📦 File Structure

```
stress-dost/
├── app.py                          # Flask backend (main logic)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── .env                           # Your credentials (created from .env.example)
├── stress_dost_triggers.txt       # Trigger dataset (JSON)
├── credentials.json               # Google Sheets credentials (optional)
├── quick_start.sh                 # Setup script (Linux/Mac)
├── SETUP_GUIDE.md                 # Detailed setup instructions
├── README.md                       # This file
└── templates/
    └── index.html                  # Frontend UI
```

---

## 🚀 Quick Start

### 1. Installation (1 minute)

```bash
# Clone/download project
cd stress-dost

# Run quick start script (Mac/Linux)
bash quick_start.sh

# Or manually:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration (2 minutes)

```bash
# Edit .env file with your keys
nano .env  # or use your text editor

# Required (free):
OPENAI_API_KEY=sk-your-key-from-https://platform.openai.com/api-keys

# Optional (for data logging):
GOOGLE_SHEET_ID=your-sheet-id
GOOGLE_SHEETS_CREDENTIALS_PATH=./credentials.json
```

### 3. Run (1 minute)

```bash
python app.py
# Visit http://localhost:5000
```

**Total time: ~5 minutes** ✅

---

## 🔧 Customization

### Change Meter Threshold

Edit `.env`:
```
METER_THRESHOLD=0.8  # When to consider student highly stressed
```

### Adjust Difficulty Increment

Edit `.env`:
```
DIFFICULTY_INCREMENT=0.1  # How much to increase when performing well
```

### Modify Trigger Dataset

Edit `stress_dost_triggers.txt`:
```json
{
  "thoughts": {
    "new_trigger": {
      "type": "option_based",
      "text": "Your trigger text here",
      "options": ["option1", "option2", "option3"],
      "value": 0.7
    }
  }
}
```

### Customize ChatGPT Behavior

Edit `app.py` in `get_chatgpt_trigger()`:
```python
context = f"""
Customize this prompt based on your needs...
"""
```

---

## 📊 Data Stored

For each student session, Stress Dost stores:

```json
{
  "session_id": "user_123_1234567890",
  "user_id": "user_123",
  "duration_seconds": 1500,
  "final_meters": {
    "fear": 0.65,
    "thoughts": 0.42,
    "frustration": 0.58,
    "average": 0.55
  },
  "questions_attempted": 30,
  "triggers_shown": 35,
  "responses": [
    {
      "question_index": 1,
      "trigger_text": "What if I can't solve this?",
      "trigger_type": "option_based",
      "selected_option": 1,
      "time_taken": 2.3,
      "answer_correct": true,
      "meter_update": 0.09,
      "timestamp": "2025-11-27T21:45:30"
    }
    // ... more responses
  ]
}
```

---

## 🎓 Educational Benefits

### For Students:
1. **Self-awareness** - Understand their stress patterns
2. **Resilience building** - Practice handling pressure
3. **Coping strategies** - Learn what works for them
4. **Mental preparation** - Know what to expect on exam day
5. **Confidence boost** - Demonstrate they can handle stress

### For Educators:
1. **Identify at-risk students** - Who needs psychological support
2. **Personalized coaching** - Tailor guidance to student psychology
3. **Holistic assessment** - Beyond just academic scores
4. **Research data** - Understand stress patterns in JEE/NEET prep
5. **Intervention timing** - Know when students need most support

---

## ⚡ Performance Tips

- **Caching:** Triggers dataset is pre-loaded in memory
- **Async ChatGPT:** Requests timeout after 5 seconds
- **Database:** Use MongoDB for production (not Google Sheets)
- **CDN:** Serve frontend static files via CDN
- **Rate Limiting:** Add rate limits to prevent abuse

---

## 🔐 Security

- API keys stored in `.env` (never commit to git)
- CORS restricted to your domain (edit in `app.py`)
- Input validation on all endpoints
- WebSocket authentication ready (add as needed)
- HTTPS recommended for production

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| "ChatGPT timeout" | Check internet, verify API key, increase timeout |
| "Google Sheets not logging" | Verify credentials, sheet ID, service account access |
| "Trigger never appears" | Check triggers file exists, verify backend logs |
| "Meters not updating" | Check response format, verify calculation logic |
| "Frontend won't load" | Check backend running, CORS settings, browser console |

**For detailed troubleshooting:** See `SETUP_GUIDE.md`

---

## 📈 Next Steps

1. **Deploy to production** - Use Heroku, Render, or AWS
2. **Connect question bank** - Link your question API
3. **Add user authentication** - Implement login system
4. **MongoDB integration** - Replace Google Sheets
5. **Mobile app** - React Native or Flutter version
6. **Analytics dashboard** - Visualize stress patterns
7. **AI coaching** - Personalized recommendations based on data

---

## 📞 Support

- 📖 **Setup Issues?** → Read `SETUP_GUIDE.md`
- 🐛 **Bug Reports?** → Check logs and console
- 💡 **Feature Requests?** → Modify trigger dataset
- 🔑 **API Keys?** → See configuration section

---

## 📜 License & Attribution

This system is designed for educational purposes. It incorporates:
- Flask (Python web framework)
- SocketIO (Real-time communication)
- OpenAI ChatGPT API (AI trigger generation)
- Google Sheets API (Data storage)

---

## 📝 Version History

- **v1.0.0** (Nov 27, 2025)
  - Initial release
  - ChatGPT integration
  - Google Sheets logging
  - 3-meter psychological assessment
  - Real-time WebSocket triggers

---

**Created with ❤️ for JEE/NEET Students**

**Tagline:** *Manage Your Stress | Master Your Mind | Ace Your Exam* 🚀

---

## 🌟 Features at a Glance

| Feature | Status | Details |
|---------|--------|---------|
| Real-time Triggers | ✅ | WebSocket-based pop-ups |
| ChatGPT Integration | ✅ | 50% AI-generated triggers |
| 3-Meter System | ✅ | Fear, Thoughts, Frustration |
| Google Sheets Logging | ✅ | Automatic data storage |
| Google Sheets Template | ✅ | https://docs.google.com/spreadsheets/d/1ChBnK8WxXYJeK_WakXNIaBKiQ898RFuiqipBP1W-Zvk/edit?usp=sharing |
| Difficulty Scaling | ✅ | Adapts to performance |
| Responsive UI | ✅ | Desktop & mobile |
| Dark Mode | ✅ | Eye-friendly theme |
| Question Bank API | 🔧 | Ready to integrate |
| User Authentication | 🔧 | Need to implement |
| MongoDB Support | 🔧 | Easy to add |
| Mobile App | 🔧 | Can be built |

---

**Last Updated:** November 27, 2025  
**Status:** Production Ready ✅
