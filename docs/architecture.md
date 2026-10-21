# InformalID - Architecture

```
worker --(7 fixed questions)--> interview loop (core/profiler.py: conduct_interview)
                                   |  money answer with no number?
                                   v
                          Claude: one short follow-up (output_config effort=low)
                                   |
        transcript ----------------+
            |
            v
   Claude + tool `extract_financial_profile`            core/profiler.py: extract_profile
   (strict schema = FinancialProfile; tool_choice auto)
            |
            v  tool_use.input
   Pydantic validation (core/models.py)
      invalid -> tool_result(is_error) -> Claude retries (max 3)
      valid   -> FinancialProfile
            |
            +--> core/schemes.py  (plain Python rules; no model call) --> SchemeMatch list, JAM score
            |
            +--> core/formatter.py --> terminal card / JSON
```

## Decisions

1. **Fixed question script.** The model never decides what to ask, so every profile covers the same
   fields. Claude's roles are the follow-up for a vague money answer and the structured extraction.
2. **Tool use for extraction, with the Pydantic model as the schema.** `anthropic.transform_schema`
   turns `FinancialProfile` into a strict-compatible JSON schema. `strict: true` keeps the input
   schema-valid; Pydantic still enforces ranges and the savings/income rule, because strict mode moves
   numeric constraints into descriptions.
3. **`tool_choice` stays on `auto`.** Current Claude models (Sonnet 5.5, Opus 5.5) return a 400 for forced
   tool use. The prompt asks for exactly one call and the code checks `stop_reason` and the content
   blocks (a thinking block may come first, so blocks are read by type, never by position).
4. **Validation errors go back to the model.** An invalid input is answered with a `tool_result` that has
   `is_error: true` and the Pydantic message, and the model corrects it. After 3 attempts, or on a
   refusal or `max_tokens` stop, `ExtractionError` is raised; nothing invalid is used downstream.
5. **Eligibility is deterministic code.** The extraction prompt forbids naming schemes or amounts, so
   `core/schemes.py` is the only place scheme facts live. Occupation matching uses only the worker's own
   occupation and skills (a spouse's trade must not qualify the worker) and word boundaries (so "chai"
   does not match "chair").
6. **One code path, two clients.** `core/mock.py` supplies `ScriptedClient`, which returns real SDK
   `Message` objects. Offline runs and tests go through the same functions as live runs.

## What this is not

- Not a credit score or an approval system; the output is a starting document for an officer.
- Not connected to any government database; scheme rules are encoded by hand with sources in
  `core/schemes.py` and need periodic re-checking.

## Data handling

- The API key is read only in `config.py` (from the environment or a gitignored `.env`).
- Nothing is persisted; the profile lives in memory for the session.
- In live mode the transcript is sent to the Anthropic API and nowhere else.
