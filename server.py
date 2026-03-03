import os
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google import genai

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found. Please set it in .env")
client = genai.Client(api_key=api_key)

from src.intent_classifier import classify_intent
from src.text_to_sql import generate_sql, execute_sql
from src.analytical_rag import answer_analytical_question, build_knowledge_base

# Build the ChromaDB knowledge base on startup
build_knowledge_base(client)

app = FastAPI(title="Mobexpert AI")

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sql: str | None = None


def generate_conversational_answer(question: str, df: pd.DataFrame) -> str:
    """Uses Gemini Flash to wrap raw dataframe results into a contextual human sentence."""
    try:
        if df.empty:
            return "Nu au fost găsite date pentru această interogare."

        columns = ", ".join(df.columns.tolist())
        row_count = len(df)

        if row_count == 1 and len(df.columns) <= 2:
            data_summary = df.to_string(index=False)
            prompt = f"""Utilizatorul a întrebat: '{question}'
Baza de date a returnat: {data_summary}
Coloanele sunt: {columns}

REGULI STRICTE:
1. Scrie un răspuns clar de 1-2 propoziții în limba română.
2. REPETĂ contextul cheie din întrebare în răspuns.
3. Dacă valoarea este un procent (sub 1.0 sau coloana conține "conversie" sau "rata"), formatează-l ca procent (ex: 0.1934 → 19.34%).
4. Dacă valoarea este un număr mare, folosește separatoare de mii.
5. Nu adăuga informații inventate."""
        else:
            data_preview = df.head(5).to_string(index=False)
            prompt = f"""Utilizatorul a întrebat: '{question}'
Baza de date a returnat {row_count} rânduri. Primele rezultate:
{data_preview}
Coloanele sunt: {columns}

REGULI STRICTE:
1. Scrie un rezumat clar de 2-3 propoziții în limba română care subliniază cele mai importante valori.
2. REPETĂ contextul cheie din întrebare (perioada, magazinul, metrica).
3. Dacă este un clasament, menționează primele 1-2 pozitii.
4. Formatează procentele și numerele mari corect.
5. Nu adăuga informații inventate."""

        r = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return r.text
    except Exception:
        return "Iată datele pe care le-ai solicitat."


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    user_message = req.message.strip()

    # Step 1: Classify intent
    intent = classify_intent(client, user_message)

    if intent == "QUANTITATIVE":
        sql = generate_sql(client, user_message)
        df = execute_sql(sql)

        if isinstance(df, str):
            return ChatResponse(answer=f"Eroare SQL: {df}", intent=intent, sql=sql)

        answer = generate_conversational_answer(user_message, df)
        return ChatResponse(answer=answer, intent=intent, sql=sql)

    elif intent == "ANALYTICAL":
        try:
            ans_text, context_str, sql_data = answer_analytical_question(client, user_message)
            return ChatResponse(answer=ans_text, intent=intent)
        except Exception as e:
            return ChatResponse(answer=f"Eroare la analiza: {str(e)}", intent=intent)

    return ChatResponse(answer="Nu am putut procesa întrebarea.", intent=intent)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
