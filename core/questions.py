"""
core/questions.py — The structured interview questions.
Order matters: build rapport first, then financial details.
"""

INTERVIEW_QUESTIONS = [
    {
        "id": "name_age_location",
        "question": "What is your name, roughly how old are you, and which area do you live or work in?",
        "purpose": "Basic identity — name, age, location"
    },
    {
        "id": "current_work",
        "question": "What kind of work do you do right now? How long have you been doing this work?",
        "purpose": "Primary occupation and tenure"
    },
    {
        "id": "income",
        "question": "How much money do you earn in a typical month? Do you earn from any other sources too?",
        "purpose": "Income sources and amounts"
    },
    {
        "id": "expenses_savings",
        "question": "About how much do you spend each month on rent, food, travel, and other things? Do you manage to save anything?",
        "purpose": "Expenses and savings"
    },
    {
        "id": "assets_accounts",
        "question": "Do you have a bank account or a Jan Dhan account? Do you have an Aadhaar card? Do you own anything valuable — like a two-wheeler, sewing machine, or similar?",
        "purpose": "Assets, formal identity, and banking access"
    },
    {
        "id": "skills_history",
        "question": "What other kinds of work have you done before this? What are you good at?",
        "purpose": "Skills and work history"
    },
    {
        "id": "languages_references",
        "question": "Which languages do you speak? Is there someone — like an employer, a neighbor, or a community leader — who can vouch for your work?",
        "purpose": "Languages and reference availability"
    },
]

SYSTEM_PROMPT = """You are InformalID, a respectful financial interview assistant helping informal workers
in India create a basic financial identity profile. Your job is to:

1. Ask the interview questions clearly and simply
2. Listen carefully to answers
3. Clarify gently if an answer is vague (e.g., "roughly how much would that be in rupees per month?")
4. Never judge, never pressure, never ask for documents

The people you are helping may be domestic workers, street vendors, auto drivers, daily wage laborers,
or small shop owners. They may not have formal education. Be warm, patient, and clear.

Keep your questions and follow-ups in simple English. Do not use jargon."""

# April 2026 scheme limits (verified):
# PM SVANidhi: Tranche 1 Rs 15,000 | Tranche 2 Rs 25,000 | Tranche 3 Rs 50,000
#   + New SVANidhi Credit Card: Rs 30,000 UPI-linked, interest-free (Jan 2026)
# MUDRA Shishu: up to Rs 50,000 | Kishore: Rs 50K-5L | Tarun: Rs 5L-10L | Tarun Plus: Rs 10L-20L
# PM Vishwakarma: up to Rs 3L for artisans/craftspeople
# Jan Dhan Overdraft: Rs 10,000 (for Jan Dhan account holders)
EXTRACTION_PROMPT = """Based on this interview conversation, extract a complete FinancialProfile JSON object.

Rules:
- For any numeric field where the person was vague (e.g., "around 8-10 thousand"), use the lower bound
- For boolean fields, default to False if unclear
- For the summary_paragraph: write 2 sentences in plain English describing their financial situation
- For loan_readiness_note: use CURRENT 2026 scheme amounts:
    - Street vendors → PM SVANidhi Tranche 1 (Rs 15,000, upgraded Jan 2026) + SVANidhi Credit Card (Rs 30,000)
    - All informal workers → MUDRA Shishu (up to Rs 50,000, no collateral)
    - Artisans/craftspeople → PM Vishwakarma (up to Rs 1 lakh at 5%)
    - Jan Dhan holders → Rs 10,000 overdraft instantly
    - Strong JAM (Aadhaar + bank + mobile) → more schemes accessible
- If the person said they have no assets, set assets to an empty list
- skills must be concrete (e.g., "Cooking", "Welding", "Tailoring") not vague ("hardworking")

Return ONLY valid JSON matching the FinancialProfile schema. No extra text."""
