# PLAN: Chatbot Accuracy & UX Fixes

## Priority Order & Rationale

Fixes ordered by dependency — each phase builds on the previous one.

---

## Phase 1: Remove META Intent (Issue #5) ⏱️ ~5 min

**Why first:** Simplifies the entire codebase before we touch anything else. Less code = fewer bugs.

**What changes:**
- **`intent_classifier.py`** — Remove the `META` category from the classification prompt. Reduce to 2 intents: `QUANTITATIVE` and `ANALYTICAL`.
- **`app.py`** — Delete the `handle_meta_question()` function and the `elif intent == "META"` block entirely.
- **Sidebar** — Remove the example "Cum se calculează rata de conversie?" from the sidebar tips.

---

## Phase 2: Improve SQL Accuracy for Complex Queries (Issue #3) ⏱️ ~15 min

**Why second:** The brain must be accurate before we polish the answers.

**What changes:**
- **`text_to_sql.py` → `SCHEMA_PROMPT`** — Expand the prompt with explicit rules for complex calculations:

| Query Type | Required SQL Logic |
|---|---|
| Average conversion per day in date range | `SELECT Data, SUM("Nr Clienti Unici") / SUM(avgTrafficIn) ... WHERE Data BETWEEN X AND Y GROUP BY Data` |
| All-time conversion for a specific store | `SELECT SUM("Nr Clienti Unici") / SUM(avgTrafficIn) ... WHERE Magazin LIKE '%Baneasa%'` |
| Best hour by traffic across all stores | `SELECT Ora, Minut, AVG(avgTrafficIn) ... GROUP BY Ora, Minut ORDER BY 2 DESC LIMIT 1` |
| Weighted conversion rate | Must NOT average `Conversie %` directly — must always compute `SUM(clients) / SUM(traffic)` |

- Add explicit **anti-rules**: "NEVER use `AVG(Conversie %)` — always recompute from raw columns."
- Add **date handling rules**: "When user says 'de la X până la Y', use `WHERE Data BETWEEN 'X' AND 'Y'`."
- Add **fuzzy store matching**: "When user mentions a store name, use `LIKE '%keyword%'` not exact match."

---

## Phase 3: Better Answer Formatting (Issue #2) ⏱️ ~10 min

**Why third:** Now that SQL returns correct data, we improve how AI presents it.

**What changes:**
- **`app.py` → `generate_conversational_number()`** — Rewrite the prompt to force contextual answers:

```
Current: "Rata de conversie a fost 0.19."
Target:  "Rata de conversie din totalul persoanelor care au intrat în magazin a fost de 19.34%."
```

- New prompt template will include:
  1. The original user question (for context echoing)
  2. The column names from the DataFrame (so AI knows what metric it's reporting)
  3. Explicit instruction: "Repeat the key context from the question in your answer. Format percentages as %. Format large numbers with separators."
- Handle **multi-row results** — instead of just "Iată datele", generate a brief summary sentence.

---

## Phase 4: Hide Raw DataFrame from Chat (Issue #1) ⏱️ ~5 min

**Why fourth:** Cosmetic fix, depends on Phase 3 being done (since the AI answer now carries the full context).

**What changes:**
- **`app.py`** — For `QUANTITATIVE` responses:
  - **Remove** `st.dataframe(df, use_container_width=True)` from the main chat area (line 110).
  - **Keep** the dataframe **only inside** the expandable "Vezi Traducerea AI în SQL" section, so power users can still inspect raw data if they want.
- For session history replay: same logic — don't show `df` in the main chat, only inside expander.

---

## Phase 5: UI Overhaul (Issue #4) 🔒 DEFERRED

**Status:** Blocked — waiting for reference photos from user.

**When ready:** User will provide reference designs, and we will completely restyle the chat interface, chatbox, loading animations, and overall layout.

---

## Execution Order Summary

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → [Phase 5 later]
 Remove     Fix SQL    Better     Hide      UI
 META       accuracy   answers    table     overhaul
```

## Verification

After each phase, test with these queries:
1. `"Care a fost rata de conversie din toate magazinele?"` — should return a contextual sentence, no ugly table
2. `"Care este ora cu cel mai mare trafic din toate magazinele?"` — complex aggregation test
3. `"Care a fost rata de conversie medie pe zi de la 01.02 până la 15.02?"` — date range + daily breakdown
4. `"Care a fost rata de conversie totală în Baneasa?"` — fuzzy store match test
