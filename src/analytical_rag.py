import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai
from src.text_to_sql import generate_sql, execute_sql

class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Custom embedding function for ChromaDB that uses Gemini text-embedding-004.
    """
    def __init__(self, client: genai.Client):
        self.client = client
        
    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model='gemini-embedding-001',
            contents=input,
        )
        # Returns a list of vectors
        return [e.values for e in response.embeddings]

def get_collection(client: genai.Client):
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    return chroma_client.get_or_create_collection(
        name="retail_knowledge",
        embedding_function=GeminiEmbeddingFunction(client)
    )

# 3. Our Mock Knowledge Base (Pre-computed summaries & Meta definitions)
KNOWLEDGE_BASE = [
    {
        "id": "insight_february",
        "text": "TENDINȚĂ LUNARĂ - FEBRUARIE: În februarie, furtunile de zăpadă severe din regiune au provocat închiderea timpurie a multor magazine, ducând la o scădere semnificativă atât a traficului (avgTrafficIn) cât și a vânzărilor în toate regiunile."
    },
    {
        "id": "insight_pipera",
        "text": "COMPARAȚIE MAGAZINE: Mobexpert Pipera este magazinul principal și are, în general, cel mai mare trafic și cea mai mare valoare medie a comenzii (Valoare medie pe Client). Magazinele de tip boutique mai mici au rate de conversie mai mari, dar un trafic total mai mic."
    },
    {
        "id": "rule_conversion",
        "text": "DEFINIȚIE - RATA DE CONVERSIE: Valoarea procentuală „Conversie %” este calculată împărțind „Nr Clienti Unici” (Clienți unici care au cumpărat) la „avgTrafficIn” (Trafic total/Persoane care au intrat). Aceasta reprezintă procentajul de vizitatori care au făcut o achiziție."
    },
    {
        "id": "rule_refunds",
        "text": "DEFINIȚIE - RETURURI: Veniturile negative (Valoare Comenzi_Bonuri) indică faptul că valoarea totală a articolelor returnate a depășit valoarea noilor articole achiziționate în acel interval specific."
    }
]

def build_knowledge_base(client: genai.Client):
    """Inserts our knowledge base into ChromaDB if it's empty."""
    collection = get_collection(client)
    if collection.count() == 0:
        print("-> Building Vector Database...")
        ids = [item["id"] for item in KNOWLEDGE_BASE]
        documents = [item["text"] for item in KNOWLEDGE_BASE]
        
        collection.upsert(
            documents=documents,
            ids=ids
        )
        print(f"-> Saved {len(documents)} documents to ChromaDB.")
    else:
        print(f"-> Vector DB already initialized with {collection.count()} documents.")

def search_knowledge(client: genai.Client, query: str, n_results: int = 2) -> list[str]:
    """Given a natural language query, find the most semantically relevant documents."""
    collection = get_collection(client)
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    # The documents are returned in a nested list
    if results["documents"]:
        return results["documents"][0]
    return []

def answer_analytical_question(client: genai.Client, user_question: str) -> tuple[str, str, object]:
    """
    The HYBRID Pipeline:
    1. Grabs semantic context from Vector DB (Chroma)
    2. Generates SQL to get hard numbers from Data DB (DuckDB)
    3. Feeds BOTH to Gemini Pro to reason and write the final answer.
    """
    # --- STEP 1: SEMANTIC RETRIEVAL ---
    context_docs = search_knowledge(client, user_question)
    context_str = "\n".join([f"- {doc}" for doc in context_docs])
    
    # --- STEP 2: SQL RETRIEVAL ---
    sql_query = generate_sql(client, user_question)
    sql_data = execute_sql(sql_query)
    
    # --- STEP 3: LLM REASONING ---
    prompt = f"""
    Ești un analist expert de date în retail (Retail Data Analyst).
    
    ÎNTREBAREA UTILIZATORULUI: {user_question}
    
    CONTEXT DE BUSINESS RELEVANT (Din Baza de Cunoștințe):
    {context_str}
    
    DATE BRUTE (Din Baza de Date SQL):
    {sql_data}
    
    INSTRUCȚIUNI:
    1. Răspunde la întrebarea utilizatorului direct și concis, EXCLUSIV ÎN LIMBA ROMÂNĂ.
    2. Folosește 'DATE BRUTE' pentru a aduce numere și fapte concrete.
    3. Folosește 'CONTEXT DE BUSINESS RELEVANT' pentru a explica *DE CE* se întâmplă acele numere sau pentru a defini termeni.
    4. Dacă datele brute contrazic contextul, ai încredere în datele brute pentru numere, dar folosește contextul pentru a explica de ce ar putea să apară acea situație.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    
    return response.text, context_str, sql_data


if __name__ == "__main__":
    # Ensure the DB is populated
    build_knowledge_base()
    
    # Test our Hybrid RAG!
    test_q1 = "Why was traffic and revenue low in February?"
    test_q2 = "Is a negative revenue in the data a mistake, or what does it mean? Did it happen in Mobexpert Pipera?"
    
    answer_analytical_question(test_q1)
    answer_analytical_question(test_q2)
