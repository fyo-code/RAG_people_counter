# Hybrid RAG Chatbot — People Counter Analytics

> A step-by-step decision analysis for building a hybrid RAG system over structured retail analytics data (CSV), powered by Gemini.

---

## 1. Understanding The Problem (Context Analysis)

### What You Have
| Asset | Details |
|-------|---------|
| **Data** | CSV files, ~70K rows, ~12-13 MB |
| **Domain** | Retail foot traffic — entries, gender, time, conversion, multi-store |
| **Users** | Store employees (specific questions) + Executives (pattern questions) |
| **LLM Provider** | Google Gemini (3 Pro / 3 Flash / 3.1 Pro) |
| **Priorities** | 1. Accuracy, 2. Learnability |

### What You Need
A chatbot that answers **two fundamentally different question types**:

| Type | Example | Challenge |
|------|---------|-----------|
| **Quantitative** | "What was total footfall in Store X last Tuesday?" | Needs *exact* number retrieval, zero hallucination |
| **Pattern/Analytical** | "How does conversion rate change seasonally across stores?" | Needs *aggregation*, *comparison*, *trend detection* |

> [!IMPORTANT]
> This distinction is the **single most critical design decision** in your RAG. It drives everything else.

---

## 2. Decision #1 — RAG Approach

### Why "Standard RAG" Fails for Your Case

Standard RAG works like this: chunk documents → embed chunks → search by similarity → pass to LLM.

**Problem with CSV data:**
- **Semantic collapse** — Row 1 says `Store: Bucharest, Jan, 500 entries`. Row 2 says `Store: Bucharest, Feb, 480 entries`. These are *semantically almost identical* to an embedding model, but the answer changes completely.
- **Embedding swamping** — When you search "footfall in January," you get 50 near-identical rows from different stores instead of the one specific row you need.
- **Aggregation impossible** — If someone asks "total Q1 footfall," RAG would need to retrieve *every* relevant row and sum them. Standard RAG retrieves top-K chunks (e.g., 5-10), not all matching rows.

> **Verdict:** Standard RAG over raw CSV = ❌ **Bad choice for structured numerical data.**

---

### Three Architecture Options

#### Option A: Pure Text-to-SQL (No Embeddings)

```
User Question → LLM generates SQL → Query Database → LLM formats answer
```

**How it works:** Load CSV into SQLite/DuckDB. The LLM translates natural language to SQL. Execute SQL. Return results.

✅ **Pros:**
- 100% accurate for quantitative questions (SQL is deterministic)
- No embedding cost, no vector DB
- Simple to build and debug
- Perfect for aggregations (SUM, AVG, GROUP BY)

❌ **Cons:**
- Fails on vague/conversational questions ("how's the store doing?")
- LLM SQL generation can produce wrong queries (syntax errors, wrong column names)
- No semantic understanding — can't handle "busy days" → high footfall mapping
- Brittle: schema changes break everything

📊 **Effort:** Low
📊 **Accuracy for your data:** High for quantitative, Low for analytical

---

#### Option B: Hybrid RAG (Your Original Idea — Keyword + Semantic Embeddings)

```
User Question → [Keyword Search (BM25)] + [Semantic Search (Embeddings)]
             → Reciprocal Rank Fusion → Top-K chunks → LLM generates answer
```

**How it works:** Embed CSV rows as enriched text chunks. At query time, run both BM25 (keyword match) and vector similarity search. Merge results using Reciprocal Rank Fusion (RRF). Send top chunks to LLM.

✅ **Pros:**
- Handles both specific and vague queries
- Contextual embeddings understand "busy" = high footfall
- Keyword search catches exact store names, dates
- Industry-standard approach, well-documented

❌ **Cons:**
- **Still can't aggregate.** Asking "total Q1 footfall" retrieves ~10 chunks, not all 70K rows. The LLM would *guess* the total from a sample → **inaccurate.**
- Embedding 70K rows is expensive and slow to update
- Semantic collapse problem remains for highly similar rows
- Over-engineered for what is fundamentally a *database query problem*

📊 **Effort:** High
📊 **Accuracy for your data:** Medium — great for "what" questions, unreliable for "how much" questions

---

#### Option C: Hybrid SQL + Semantic RAG (Recommended ✅)

```
User Question → Intent Classifier (LLM)
                  ├── [QUANTITATIVE] → Text-to-SQL → Execute → Format answer
                  └── [ANALYTICAL]   → Semantic RAG → Retrieve context → LLM reasons
                  └── [MIXED]        → SQL first (get data) → RAG enriches reasoning
```

**How it works:** A lightweight intent classifier (can be a Gemini prompt) routes the question to the right pipeline:

| Intent | Pipeline | Why |
|--------|----------|-----|
| Quantitative ("how many", "what was the total") | Text-to-SQL | Deterministic accuracy |
| Analytical ("why", "what patterns", "compare") | SQL aggregation + LLM reasoning | Get real data, then reason over it |
| Conversational ("how's the store doing") | Pre-computed summaries + LLM | Fast, cached responses |

✅ **Pros:**
- **Best accuracy**: Numbers come from SQL (deterministic), patterns come from LLM reasoning over real aggregated data
- Each question type gets the optimal retrieval method
- You learn *both* RAG and Text-to-SQL — fulfills your learning goal
- Extensible: add new intent types without rebuilding everything
- Context caching works beautifully here (schema + instructions stay constant)

❌ **Cons:**
- More complex architecture (2 pipelines)
- Intent misclassification can route to wrong pipeline
- Requires good schema documentation for SQL generation

📊 **Effort:** Medium-High
📊 **Accuracy for your data:** **Highest possible** — deterministic for numbers, intelligent for patterns

---

### 💡 Recommendation: Option C — Hybrid SQL + Semantic RAG

**Why this is the right choice for YOUR specific case:**

1. **Your data is structured** — CSV with clear columns. This is *exactly* what SQL was designed for. Forcing structured data through an embedding pipeline is like using Google Translate to read a language you already speak.

2. **Accuracy is priority #1** — For questions like "what was the conversion rate in Store X in March?", there is *one correct answer*. SQL gives you that answer with 100% reliability. Embeddings give you "approximately correct" at best.

3. **You want to learn** — Option C teaches you the most: intent classification, text-to-SQL, semantic search, prompt engineering, and how they *compose together*. It's not just "another RAG" — it's an intelligent routing system.

4. **Gemini 3 Flash is perfect for routing** — Use Flash (fast, cheap) for intent classification. Use Pro for complex SQL generation and analytical reasoning. This dual-model approach is cost-efficient.

---

## 3. Decision #2 — Your Original Hybrid Approach Assessment

> You proposed: hybrid retrieval with keyword search + contextual embeddings.

### Verdict: **Partially correct, but needs refinement**

| Your Idea | Assessment | Explanation |
|-----------|------------|-------------|
| **Keyword search** | ✅ Good instinct | Essential for exact store names, dates, product codes |
| **Contextual embeddings** | ⚠️ Partially applicable | Useful for understanding *intent* (not for retrieving CSV rows). Move embeddings to the intent classifier, not the data retrieval |
| **Hybrid retrieval** | ✅ Correct principle | But apply it as SQL + Semantic, not BM25 + Semantic. Your data is structured — use structured retrieval |

**What contextual embeddings SHOULD be used for in your system:**
- Embedding pre-computed analytical summaries (not raw rows)
- Embedding store descriptions, business rules, metric definitions
- Enabling "fuzzy" understanding of business jargon → SQL column mapping

**What contextual embeddings should NOT be used for:**
- Retrieving specific numbers from 70K rows (use SQL)
- Aggregating data (use SQL GROUP BY)

---

## 4. Decision #3 — Prompt Caching Deep Dive

> You asked: will prompt caching add complexity? Affect accuracy? Reduce latency?

### How Gemini Context Caching Works

```
┌─────────────────────────────────────────┐
│           YOUR PROMPT (every call)       │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  CACHED PART (schema, rules,   │    │  ← Stored once, reused
│  │  system prompt, examples)      │    │     90% cost reduction
│  │  ~4,000-10,000 tokens          │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │  DYNAMIC PART (user question,  │    │  ← Changes every call
│  │  retrieved SQL results)        │    │     Full price
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Answers to Your Three Questions

| Question | Answer | Detail |
|----------|--------|--------|
| **Too complex?** | **No** — it's simple | Gemini has **implicit caching** (automatic, zero code changes). Just structure your prompt with static content first. For explicit caching, it's ~10 lines of code. |
| **Affect accuracy?** | **No** — caching doesn't change the prompt | The LLM sees the *exact same tokens* whether cached or not. Caching is a cost/latency optimization, not a content transformation. It's like RAM vs disk — same data, faster access. |
| **Reduce latency?** | **Yes, significantly** | Cached tokens skip the input processing pipeline. For a system prompt of ~5,000 tokens, you save ~200-500ms per request. Over hundreds of daily queries, this compounds. |

### What to Cache in Your System

| Content | Size | Cache Type | Why |
|---------|------|------------|-----|
| System prompt + persona | ~1,000 tokens | Implicit | Same every request |
| Database schema description | ~2,000 tokens | Implicit/Explicit | Rarely changes |
| SQL generation rules + examples | ~3,000 tokens | Explicit | Stable reference |
| Metric definitions (what is "conversion rate") | ~1,000 tokens | Explicit | Business logic |
| **Total cacheable** | **~7,000 tokens** | | **90% cheaper on reuse** |

### Gemini Models & Caching Minimums

| Model | Min for Implicit Cache | Min for Explicit Cache | Best Use |
|-------|----------------------|----------------------|----------|
| **Gemini 3 Flash** | 1,024 tokens | 32,768 tokens | Intent classification, simple SQL |
| **Gemini 3 Pro** | 4,096 tokens | 32,768 tokens | Complex reasoning, analytical answers |
| **Gemini 3.1 Pro** | 4,096 tokens | 32,768 tokens | Latest, most capable |

> [!NOTE]
> Your system prompt + schema (~7K tokens) exceeds the **implicit caching minimum** for both Flash (1,024) and Pro (4,096). This means you get **automatic cache hits for free** — no extra code needed. Just keep the static content at the **beginning** of your prompt.

### Verdict: **Prompt caching is a smart decision** ✅

- Zero complexity increase (implicit caching is automatic)
- Zero accuracy impact
- Meaningful latency and cost reduction
- Perfectly suited for your use case (repetitive schema + instructions)

---

## 5. Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│                   USER INTERFACE                     │
│              (Chat input / Web app)                  │
└─────────────┬───────────────────────────────────────┘
              │ User Question
              ▼
┌─────────────────────────────────────────────────────┐
│          INTENT CLASSIFIER (Gemini 3 Flash)          │
│  "What type of question is this?"                    │
│                                                      │
│  Classifies into: QUANTITATIVE | ANALYTICAL | META   │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ SQL PATH │  │ HYBRID PATH  │  │  META PATH   │
│          │  │              │  │              │
│ Gemini   │  │ SQL query    │  │ Pre-computed │
│ 3 Pro    │  │ for data +   │  │ summaries    │
│ generates│  │ LLM reasons  │  │ from cache   │
│ SQL      │  │ over results │  │              │
└────┬─────┘  └──────┬───────┘  └──────┬───────┘
     │               │                 │
     ▼               ▼                 ▼
┌─────────────────────────────────────────────────────┐
│               DATABASE (SQLite / DuckDB)             │
│                                                      │
│  CSV loaded into structured tables                   │
│  Columns: store, date, hour, gender, entries,        │
│           purchases, conversion_rate                 │
└─────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│          RESPONSE GENERATOR (Gemini 3 Pro)           │
│                                                      │
│  [CACHED: schema + rules + persona]                  │
│  [DYNAMIC: SQL results + user question]              │
│                                                      │
│  Formats answer in natural language                  │
└─────────────────────────────────────────────────────┘
```

---

## 6. Q&A: Addressing Your Concerns (DuckDB vs Embedding Everything)

### What is DuckDB?
DuckDB is an in-process SQL OLAP database management system. Think of it as SQLite, but specifically designed for fast analytical queries (aggregations, sums, averages) over tabular data like CSVs or Parquet files.
- **Why we use it:** It can run SQL queries directly on your 12MB CSV file in milliseconds *without* needing to set up a separate database server. It acts as the "facts engine" for our quantitative questions.

### The Old Way You Tried: "Embed Everything" (Naive RAG)
You mentioned a previous attempt where the system chunked the file (e.g., 100 limit per chunk) and used AI to embed every single piece of data, which took forever.

**What happened back then:**
That was a standard **Naive RAG** approach applied to structured data. The system likely:
1. Took your CSV and turned every row (or set of 100 rows) into a text string ("Store A had 500 entries on Tuesday...").
2. Sent *thousands* of requests to an embedding API (like OpenAI `text-embedding-ada-002`). This takes a long time and costs money.
3. Stored those thousands of embeddings in a Vector Database.
4. When you asked a question, it tried to find the "most similar text."

**Why it failed for your use case:** It's slow to build, expensive, and fundamentally bad at math. If you ask for a total, it retrieves 5 random chunks and hallucinates a sum, rather than summing all 70k rows.

### The New Way: Why Our System is Better
**Crucial Clarification:** In our Hybrid SQL + Semantic RAG system, **we will NOT embed every single variable or row in the CSV file.**

Here is the difference:
1. **The Raw Data (70k rows) stays in DuckDB.** It is never embedded. It is never "chunked" into text. When a user asks "How many people entered Store X?", the Gemini 3 Pro model writes a SQL query (`SELECT SUM(entries) FROM data WHERE store='X'`), DuckDB executes it instantly, and returns the exact number. Zero embeddings required.
2. **What WE will embed (The Semantic Part):** We will only use embeddings for "metadata" and "business logic."
   - We might embed a document explaining *what* a conversion rate is.
   - We might embed pre-calculated monthly summaries (e.g., "Store X had a great Q3 due to holiday foot traffic").
   - This means we are embedding a few dozen helpful documents, **not 70,000 rows**.

**Will this be better?** Yes.
- **Setup Time:** Instant. Loading a 12MB CSV into DuckDB takes less than a second. We skip the hours-long embedding process.
- **Accuracy:** 100% for numbers. SQL doesn't guess; it calculates.
- **Cost:** Drastically lower, as we aren't paying to embed 70k rows.

---

## 7. Clarifying the RAG Flow & Definitions (Your Questions Answered)

### 1. Are we doing Vector Search + Keyword Search?
**Not exactly.** The SQL path is **NOT** a "keyword search." 
- **Keyword search (BM25)** looks for words inside documents (e.g., finding the word "Bucharest" in a PDF).
- **SQL** is a deterministic mathematical query language (e.g., `SELECT conversion_rate WHERE store = 'Bucharest'`). 
So, our hybrid approach combines **Vector Search (for semantic business meaning)** and **SQL Execution (for exact, hard data)**.

### 2. Is this the correct process?
Your summary is very close, but the order of operations is slightly different. Here is the exact step-by-step process orchestrated by the Python code:

1. **User asks a question** (e.g., "How is Store X doing compared to Y?").
2. **Python sends question to INTENT CLASSIFIER** (Gemini Flash). It asks the LLM: *"Is this a math question, an analysis question, or a general meta question?"*
3. **Python receives the decision.**
   - If it's math/analysis, Python asks the Gemini Pro to generate raw SQL.
4. **Python receives the SQL.** 
5. **Python executes the SQL in DuckDB.** (LLM does not talk to DuckDB; Python is the middleman).
6. **Python gets the data back from DuckDB** (e.g., "Store X: 5%, Store Y: 2%").
7. **Python sends BOTH the user's question AND the DuckDB data back to Gemini Pro.**
8. **Gemini Pro reads the data, formats it into a nice conversational answer, and gives it to the user.**

### 3. What is the "Meta Path"?
The "Meta Path" is for questions that are *about the system or the business rules*, not about the data rows themselves. 
- Example: "How do you calculate conversion rate?" or "What stores do we currently track?"
- In this path, the system doesn't need to write SQL or look at the 70,000 rows. It just searches the Vector Database for the "metadata" (the business rule documents we embedded) and answers instantly.

### 4. What does "LLM reasons over results" mean in the Hybrid path?
If you ask an analytical question like *"Why was footfall low in February?"*
1. **SQL grabs the hard data:** Python/DuckDB returns the daily visitor numbers for February.
2. **Vector Search grabs context:** Python searches the embedded summaries and finds an embedded note saying *"Heavy snowstorms in February caused store closures."*
3. **LLM Reasons over results:** Python gives the LLM *both* the numbers (from SQL) and the context (from Vector Search). The LLM reads both and says: *"Footfall in February was only 4,000 (down 20%), primarily due to heavy snowstorms causing temporary closures."*

Does it ask an additional SQL query? Usually, no. If the first SQL query failed or the LLM realizes it needs more data to answer the prompt, we *can* build an agentic loop where it tries again, but to start, we will keep it simple: one SQL fetch, one read-and-react phase.

---

## 8. Tech Stack Decisions

| Component | Choice | Why |
|-----------|--------|-----|
| **Language** | Python | Best RAG/ML ecosystem, pandas for CSV |
| **Database** | DuckDB | Faster than SQLite for analytical queries, reads CSV natively, no server setup |
| **LLM (routing)** | Gemini 3 Flash | Fast, cheap ($0.50/M input), good enough for intent classification |
| **LLM (reasoning)** | Gemini 3 Pro | Accurate SQL generation, strong analytical reasoning |
| **Embeddings** | Gemini `text-embedding-004` | For semantic search on summaries/metadata (not raw rows) |
| **Vector Store** | ChromaDB (local) | Simple, no server, good for learning |
| **Framework** | LangChain or LlamaIndex | Optional — start without it to learn, add later for convenience |
| **Frontend** | Streamlit or Gradio | Fast UI prototyping for chatbot |

---

## 7. Learning Roadmap

> Since learnability is priority #2, here's the build order that maximizes understanding:

### Phase 1: Foundation — Text-to-SQL (Week 1)
> **Goal:** Get accurate answers for quantitative questions

- [ ] Load CSV into DuckDB
- [ ] Write schema description document
- [ ] Build Text-to-SQL prompt with Gemini 3 Pro
- [ ] Test with 20+ quantitative questions
- [ ] Implement SQL validation and error handling

**What you learn:** Prompt engineering, LLM-to-SQL generation, structured data querying

### Phase 2: Intelligence — Intent Classification (Week 2)
> **Goal:** Route questions to the right pipeline

- [ ] Build intent classifier with Gemini 3 Flash
- [ ] Define intent taxonomy (QUANTITATIVE, ANALYTICAL, META)
- [ ] Create test set of 50+ questions with labeled intents
- [ ] Measure classification accuracy
- [ ] Handle edge cases and ambiguous queries

**What you learn:** Few-shot classification, prompt design, evaluation methodology

### Phase 3: Depth — Analytical RAG Layer (Week 3)
> **Goal:** Answer pattern and trend questions intelligently

- [ ] Pre-compute analytical summaries (monthly trends, store comparisons)
- [ ] Embed summaries with Gemini embeddings
- [ ] Build semantic retrieval with ChromaDB
- [ ] Create hybrid pipeline: SQL data + semantic context → LLM reasoning
- [ ] Test with analytical questions

**What you learn:** Embeddings, vector search, RAG pipeline, hybrid retrieval

### Phase 4: Optimization — Caching & Polish (Week 4)
> **Goal:** Reduce latency and cost, polish UX

- [ ] Implement prompt structure for implicit caching
- [ ] Add conversation memory (multi-turn)
- [ ] Build response quality evaluation
- [ ] Add explicit caching for heavy queries
- [ ] Deploy with Streamlit/Gradio frontend

**What you learn:** Context caching, production optimization, evaluation frameworks

---

## 8. Verification Plan

### Automated Tests
- Intent classification accuracy test: feed 50 labeled questions, measure F1 score
- SQL generation validation: compare generated SQL output against known correct answers for 20 test queries
- End-to-end accuracy: run 30 questions through full pipeline, compare against ground truth answers

### Manual Verification
- Have store employees test with real-world questions they'd actually ask
- Compare chatbot answers against manually calculated answers from the CSV
- Test edge cases: empty results, ambiguous store names, date range queries

---

## Summary of Your Initial Ideas

| Your Idea | Verdict | Refined Version |
|-----------|---------|-----------------|
| Hybrid RAG | ✅ Correct principle | Use SQL + Semantic (not BM25 + Semantic) for structured data |
| Contextual Embeddings | ⚠️ Apply differently | Embed *summaries and metadata*, not raw CSV rows |
| Prompt Caching | ✅ Smart decision | Gemini implicit caching works automatically, zero accuracy impact, reduces latency and cost |

> [!TIP]
> **The key insight:** Your data is structured, not unstructured. The best "RAG" for structured data is a database query — which is *technically still retrieval-augmented generation*, just with SQL as the retrieval mechanism instead of vector search.
