# InformalID — Architecture

## How It Works

```
User speaks / types
        │
        ▼
┌─────────────────────────────────┐
│  core/questions.py              │
│  7 structured interview         │
│  questions, in order            │
└──────────────┬──────────────────┘
               │
        ┌──────▼──────┐
        │  Claude API  │  (or mock)
        │  (conductor) │
        └──────┬───────┘
               │ conversation transcript
               ▼
┌─────────────────────────────────┐
│  Claude API — extraction call   │
│  EXTRACTION_PROMPT + transcript │
│  → JSON matching FinancialProfile│
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  core/models.py                 │
│  FinancialProfile (Pydantic)    │
│  Validates all fields           │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  core/formatter.py              │
│  → Terminal card (human-readable│
│  → JSON (for downstream systems)│
└─────────────────────────────────┘
```

## Key Technical Decisions

### 1. Two-call architecture (interview + extraction)
The interview is conversational and free-form. The extraction is a separate, structured call
with a JSON schema enforced by Pydantic. This separation means:
- The interview can be warm and natural (no schema leaking into the conversation)
- The extraction is deterministic and validatable
- If extraction fails to parse, we catch `json.JSONDecodeError` and can retry the extraction
  call without redoing the interview

### 2. Pydantic for schema enforcement
Every field in `FinancialProfile` has a type. If Claude returns bad JSON (missing field,
wrong type), Pydantic raises a `ValidationError` immediately — no silent bad data.
This is important because the output of this tool may be used for loan decisions.

### 3. Mock mode by default
If `ANTHROPIC_API_KEY` is not set, the tool runs entirely offline with a realistic sample
profile. This means:
- The demo always works, even in an interview with no internet
- CI tests never make API calls
- The mock data is realistic enough to show the full value of the tool

## What This Is NOT

- Not a credit scoring model (no ML, no training data)
- Not connected to any government database
- Not a loan approval system

It is a structured intake tool. The output is a starting document — a loan officer
or microfinance institution still needs to verify the information.

## Data Flow Security

- API key loaded ONLY in `config.py`
- No user data is logged
- No data is persisted to disk (profile only exists in memory during the session)
- The tool never connects to any external service except the Anthropic API (in live mode)
