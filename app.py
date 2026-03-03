import os
import time
import pandas as pd
import streamlit as st

# We set the page config first.
st.set_page_config(
        page_title="Asistent Insights Retail", 
        page_icon="📊", 
        layout="centered"
)
from dotenv import load_dotenv
load_dotenv() # Load variables from .env into the environment here

from src.intent_classifier import classify_intent
from src.text_to_sql import generate_sql, execute_sql
from src.analytical_rag import answer_analytical_question, search_knowledge
from google import genai
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment. Please ensure .env file exists and is formatted correctly.")
client = genai.Client(api_key=api_key)

def generate_conversational_answer(question: str, df: pd.DataFrame) -> str:
    """Uses Gemini Flash to wrap raw dataframe results into a contextual human sentence."""
    try:
        if df.empty:
            return "Nu au fost găsite date pentru această interogare."
        
        # Build context about what the data contains
        columns = ", ".join(df.columns.tolist())
        row_count = len(df)
        
        if row_count == 1 and len(df.columns) <= 2:
            # Single result — format it nicely
            data_summary = df.to_string(index=False)
            prompt = f"""Utilizatorul a întrebat: '{question}'
Baza de date a returnat: {data_summary}
Coloanele sunt: {columns}

REGULI STRICTE:
1. Scrie un răspuns clar de 1-2 propoziții în limba română.
2. REPETĂ contextul cheie din întrebare în răspuns. De exemplu, dacă întreabă despre "rata de conversie din toate magazinele", răspunsul trebuie să menționeze "din toate magazinele".
3. Dacă valoarea este un procent (sub 1.0 sau coloana conține "conversie" sau "rata"), formatează-l ca procent (ex: 0.1934 → 19.34%).
4. Dacă valoarea este un număr mare, folosește separatoare de mii (ex: 1234567 → 1,234,567).
5. Nu adăuga informații inventate. Folosește doar datele returnate."""
        else:
            # Multi-row result — generate a brief summary
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
        return "Iată datele pe care le-ai solicitat:"



# --- UI LAYOUT ---
st.title("📊 Asistent Insights Retail")
st.markdown("Întreabă-mă orice despre trafic, venituri sau performanța magazinelor.")

with st.sidebar:
    st.header("Starea Sistemului")
    st.success("🟢 DuckDB Conectat (126k rânduri)")
    st.success("🟢 ChromaDB Activ (Baza de Cunoștințe)")
    st.info("💡 **Încearcă să întrebi:**\n- Care a fost traficul total în toate magazinele?\n- Care este ora cu cel mai mare trafic?\n- Care a fost rata de conversie în Baneasa?")

# --- SESSION STATE (Memory) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sql" in message:
            with st.expander("⚙️ Vezi Procesul de Gândire AI"):
                st.code(message["sql"], language="sql")
                if "df" in message and isinstance(message["df"], pd.DataFrame):
                    st.dataframe(message["df"], use_container_width=True)
        if "context" in message:
            with st.expander("🧠 Vezi Contextul Semantic Utilizat"):
                st.info(message["context"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Adresează o întrebare despre datele de retail..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Process AI Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Analizez intenția..."):
            intent = classify_intent(client, prompt)
            
        if intent == "QUANTITATIVE":
            with st.spinner("Scriu SQL & Extrag Datele..."):
                sql = generate_sql(client, prompt)
                df = execute_sql(sql)
                
                if isinstance(df, str): # It's an error message
                    response_text = f"A apărut o eroare la executarea interogării:\n```text\n{df}\n```"
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text, "sql": sql})
                else:
                    response_text = generate_conversational_answer(prompt, df)
                    st.markdown(response_text)
                    with st.expander("⚙️ Vezi Traducerea AI în SQL"):
                        st.code(sql, language="sql")
                        st.dataframe(df, use_container_width=True)
                    st.session_state.messages.append({"role": "assistant", "content": response_text, "sql": sql, "df": df})
                    
        elif intent == "ANALYTICAL":
            with st.spinner("Corelare Reguli Semantice & Date SQL..."):
                try:
                    ans_text, context_str, sql_data = answer_analytical_question(client, prompt)
                    st.markdown(ans_text)
                    
                    with st.expander("🧠 Vezi Context și Date"):
                        st.info(f"**Regula Semantică găsită:**\n{context_str}")
                        st.write("**Date Extrase:**")
                        st.dataframe(sql_data, use_container_width=True)
                        
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": ans_text, 
                        "context": context_str, 
                        "df": sql_data if isinstance(sql_data, pd.DataFrame) else None
                    })
                except Exception as e:
                    st.error(f"Eroare la formularea răspunsului analitic: {e}")
                    

