# InformalID — AI financial profiler for India's cash-only informal workers

## The Problem

India has 490 million informal workers — domestic workers, street vendors, daily wage laborers,
auto drivers — who earn real money but are invisible to the financial system. They have no payslips,
no bank statements, and sometimes no bank account at all.

Every existing AI credit-scoring tool in India (Kaleidofin, FlexiLoans, UPI-based scoring) still
requires a digital footprint: UPI transactions, bank statements, or GST filings. This leaves the
truly informal — people paid daily in cash, people who don't use smartphones for payments — with
nothing. No loan history. No identity proof beyond Aadhaar. No way to show a lender they're
creditworthy even after 8 years of steady work.

The PM SVANidhi scheme exists to give micro-loans to street vendors (up to Rs 10,000). MUDRA loans
exist for small businesses. But loan officers spend hours manually capturing the same information
that InformalID captures in a 5-minute conversation — and for the most excluded workers, there's
no intake tool at all.

## What This Solves

InformalID conducts a 7-question structured conversation with a worker, then uses Claude to extract
a complete, structured financial identity card — no documents required as input.

```
[InformalID] What kind of work do you do right now? How long have you been doing this work?
[Meena Devi] I clean houses. I go to 3 houses every day. I have been doing this for 8 years.

[InformalID] How much money do you earn in a typical month?
[Meena Devi] Around 9,000 rupees per month.

→ Generates:
   ══════════════════════════════════════════════════════════════
     INFORMALID — FINANCIAL IDENTITY CARD
   ══════════════════════════════════════════════════════════════
     Name:              Meena Devi
     Occupation:        Domestic worker (house cleaning)
     Total monthly income:   Rs 9,000
     Monthly savings:        Rs 2,000
     Loan readiness:    Eligible for PM SVANidhi up to Rs 10,000
   ══════════════════════════════════════════════════════════════
```

## How It Works

```
User answers 7 questions
        │
        ▼
Claude conducts interview (natural, warm, no jargon)
        │
        ▼
Claude extracts structured JSON from transcript
        │
        ▼
Pydantic validates every field (no silent bad data)
        │
        ▼
Formatted card + JSON output (for loan officers / MFIs)
```

**3 key decisions:**
- Two-call architecture: interview is conversational; extraction is a separate structured call → schema doesn't leak into the conversation
- Pydantic validation: if extraction fails, it fails loudly — no silent bad data used for financial decisions
- Mock mode by default: demo always works with no API key, using a realistic sample persona

## Run It

```bash
git clone [private — available on request]
cd informalid
cp .env.example .env  # add your ANTHROPIC_API_KEY
pip install -r requirements.txt
python demo/demo.py
```

Demo runs in mock mode without an API key — shows a full sample interview + formatted card.

## Technical Decisions

**1. Claude for extraction, not a regex or rules engine**
The same information comes out of an interview in a thousand different ways ("I earn around eight to nine thousand" vs "9k per month" vs "three thousand a week"). Claude handles all of this naturally. A rules engine would need hundreds of edge cases.

**2. Pydantic schema as the contract**
The `FinancialProfile` model defines exactly what fields exist and what types they must be. If Claude's extraction is malformed, `ValidationError` is raised immediately — not silently stored. This is important because the output influences real financial decisions.

**3. Separation of interview and extraction into two API calls**
Combining them would mean the user sees a JSON schema mid-conversation (bad UX and confusing).
Separating them means: the interview feels human, the extraction is machine-precise.

## Tests

```bash
pytest tests/ -v

# Expected output:
# tests/test_core.py::TestFinancialProfileModel::test_mock_profile_is_valid PASSED
# tests/test_core.py::TestFinancialProfileModel::test_income_math PASSED
# ... (20+ tests)
# tests/test_integration.py::test_full_mock_pipeline PASSED
# tests/test_integration.py::test_profile_values_are_internally_consistent PASSED
```

## What's Missing / What's Next

1. **Hindi/Kannada/Tamil language support** — the questions should be in the worker's language, not English. Claude supports this but the question templates need translation and the extraction prompt needs adjustment.

2. **Output as a PDF** — a terminal card is a demo. A real loan officer needs a printable PDF with a QR code linking to the JSON record. This is a 2-hour addition (reportlab or weasyprint).

3. **Verification layer** — the profile is self-reported and unverified. A real deployment would need a microfinance officer to confirm 2-3 facts. The tool should output a "verification checklist" alongside the card.
