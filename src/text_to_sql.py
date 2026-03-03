import duckdb
from google import genai
from google.genai import types

# The Schema Prompt is the "Cached Part" from our plan. 
# It tells the LLM EXACTLY what the columns mean, based on your answers.
SCHEMA_PROMPT = """
You are an expert Data Analyst and SQL generator.
We have a DuckDB database named 'retail_data.db' with a table called 'retail_traffic'.
Your task is to write ONLY valid DuckDB SQL queries to answer the user's question.

DATABASE SCHEMA FOR 'retail_traffic'
- Data (DATE): The date of the record. DuckDB stores it as DATE type.
- Magazin (VARCHAR): The name of the specific store (e.g., "Mobexpert Pipera", "Mobexpert Baneasa", "Mobexpert Baia Mare").
- Luna (BIGINT): The month number (1-12).
- An (BIGINT): The year (e.g., 2025).
- ZiLuna (BIGINT): Day of the month (1-31).
- Minut (BIGINT): The minute of the hour (0, 15, 30, 45). Data is in 15-min intervals.
- Ora (BIGINT): The hour of the day (e.g., 10, 11... 19). Stores are open roughly 10-20.
- avgTrafficIn (BIGINT): ABSOLUTE count of ALL people who entered the store in that 15-min interval. This includes both genders. To get total traffic, use SUM(avgTrafficIn).
- Female (DOUBLE): Number of FEMALE visitors who entered the store in that interval. This is a subset of avgTrafficIn.
- Male (DOUBLE): Number of MALE visitors who entered the store in that interval. This is a subset of avgTrafficIn.
- "Male %" (DOUBLE): Percentage of traffic that was male in that interval. Value like 0.5 means 50% male. Female % = 1 - "Male %".
- "Valoare Comenzi_Bonuri" (DOUBLE): Net revenue/value of orders in that interval. Negative = refunds exceeded sales. To get total revenue, SUM this.
- "Conversie %" (DOUBLE): Pre-calculated conversion rate for ONE interval only. Value like 0.14 means 14%.
- "Valoare medie pe Client" (DOUBLE): Average Order Value per unique client in that interval.
- "Nr Clienti Unici" (BIGINT): Number of unique clients who made a purchase in that interval.


═══════════════════════════════════════════════════
CRITICAL ANTI-RULES (NEVER VIOLATE THESE):
═══════════════════════════════════════════════════

1. NEVER use AVG("Conversie %") to compute aggregate conversion rates across multiple rows.
   The "Conversie %" column is only valid for its own single 15-min interval.
   To compute conversion rate across ANY aggregation (by day, by store, by week, overall),
   you MUST always use: SUM("Nr Clienti Unici") / NULLIF(SUM(avgTrafficIn), 0)

2. NEVER use AVG("Valoare medie pe Client") for aggregate average ticket.
   Instead use: SUM("Valoare Comenzi_Bonuri") / NULLIF(SUM("Nr Clienti Unici"), 0)

3. NEVER use AVG(avgTrafficIn) when user asks for "total traffic". Always SUM.

4. NEVER use AVG("Male %") to compute aggregate male percentage across rows.
   Instead use: SUM(Male) / NULLIF(SUM(Female) + SUM(Male), 0)
   Similarly for female percentage: SUM(Female) / NULLIF(SUM(Female) + SUM(Male), 0)
   IMPORTANT: Do NOT divide by SUM(avgTrafficIn). The gender sensor does not classify
   every visitor, so SUM(Female)+SUM(Male) may differ from SUM(avgTrafficIn).
   Always use SUM(Female)+SUM(Male) as the denominator for gender percentages.

═══════════════════════════════════════════════════
QUERY PATTERN RULES:
═══════════════════════════════════════════════════

CRITICAL — TRAFFIC vs CLIENTS DISTINCTION:
These are TWO COMPLETELY DIFFERENT metrics. NEVER confuse them.

  "trafic", "oameni", "vizitatori", "persoane", "intrări", "câți au intrat"
    → Use SUM(avgTrafficIn). This counts ALL people who entered the store,
      regardless of whether they bought anything.

  "clienți", "cumpărători", "conversii", "câți au cumpărat", "câți clienți"
    → Use SUM("Nr Clienti Unici"). This counts ONLY people who made a purchase.

  Example: "Câți oameni au intrat?" → SUM(avgTrafficIn)
  Example: "Câți clienți au fost?"  → SUM("Nr Clienti Unici")

GENDER QUERIES:
  "bărbați", "masculin", "male", "câți bărbați"
    → Use SUM(Male). These are MALE visitors (subset of gender-classified traffic).

  "femei", "feminin", "female", "câte femei"
    → Use SUM(Female). These are FEMALE visitors (subset of gender-classified traffic).

  "procentul de bărbați", "% masculin"
    → Use ROUND(SUM(Male) / NULLIF(SUM(Female) + SUM(Male), 0) * 100, 2) to get male %.

  "procentul de femei", "% feminin"
    → Use ROUND(SUM(Female) / NULLIF(SUM(Female) + SUM(Male), 0) * 100, 2) to get female %.

  NOTE: Gender columns (Male, Female) count VISITORS, not buyers. They are independent of conversions.
  NOTE: Not all visitors are gender-classified. SUM(Female)+SUM(Male) may be less than SUM(avgTrafficIn).


STORE NAME MATCHING:
- When user mentions a store name (e.g., "Baneasa", "Pipera", "Militari"),
  use ILIKE '%keyword%' for fuzzy matching. Example: WHERE Magazin ILIKE '%baneasa%'
- Do NOT require exact match. The user will use casual store names.

DATE RANGES:
- When user says "de la X până la Y", "între X și Y", or "din data X până în Y":
  use WHERE Data BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
- If user gives dates like "01.02" without year, assume 2024. Convert to 'YYYY-MM-DD'.
- If user says "luna februarie" (month of February), use: WHERE MONTH(Data) = 2

BEST HOUR / PEAK TIME QUERIES:
- When user asks "care este ora cu cel mai mare trafic" or "best hour" or "ora de vârf":
  SELECT Ora, ROUND(AVG(avgTrafficIn), 2) as trafic_mediu
  FROM retail_traffic
  GROUP BY Ora
  ORDER BY trafic_mediu DESC
  LIMIT 1
- If they want 15-min granularity, also group by Minut.

PER-DAY BREAKDOWNS:
- When user asks for "pe zi" / "pe fiecare zi" / "zilnic" / "per day":
  GROUP BY Data and ORDER BY Data.

RANKING / TOP QUERIES:
- "clasament", "top", "cel mai bun", "cel mai rau" → ORDER BY ... DESC/ASC LIMIT N

═══════════════════════════════════════════════════
OUTPUT RULES:
═══════════════════════════════════════════════════

1. ALWAYS return ONLY the raw SQL query string. No markdown, no backticks, no explanation.
2. The table name is retail_traffic.
3. Column names with spaces or special characters MUST be quoted: "Valoare Comenzi_Bonuri", "Nr Clienti Unici", "Conversie %", "Valoare medie pe Client", "Male %".
4. Understand the user's prompt in Romanian. Map Romanian terms for days/months/metrics to schema columns.
5. Use ROUND() for decimal results to keep output clean.
6. For month filtering, use the Luna column (1-12). For year filtering, use the An column.
"""

def generate_sql(client: genai.Client, user_question: str) -> str:
    """Takes a user question and asks Gemini to turn it into a DuckDB SQL query."""
    print(f"-> Asking Gemini to translate: '{user_question}'")
    
    # We use Gemini 3 Pro (or 2.5 Pro as standard alias) for complex reasoning
    # We pass the schema carefully as System Instruction cacheable context
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=user_question,
        config=types.GenerateContentConfig(
            system_instruction=SCHEMA_PROMPT,
            temperature=0.0  # We want deterministic, exact SQL, not creative SQL
        )
    )
    
    sql_query = response.text.strip()
    
    # Clean up markdown if the LLM disobeys the instruction
    if sql_query.startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    elif sql_query.startswith("```"):
        sql_query = sql_query.replace("```", "").strip()
        
    return sql_query

def execute_sql(sql_query: str, db_path: str = "retail_data.db"):
    """Connects to the DuckDB file and executes the generated SQL."""
    print(f"-> Executing SQL in DuckDB:\n{sql_query}\n")
    try:
        con = duckdb.connect(db_path)
        # We fetch the result as a Pandas DataFrame for easy reading in terminal
        result = con.execute(sql_query).df()
        con.close()
        return result
    except Exception as e:
        return f"Error executing SQL: {str(e)}"

def ask_database(client: genai.Client, question: str):
    """The main orchestration function for the Text-to-SQL pipeline."""
    print("=" * 60)
    sql = generate_sql(client, question)
    result = execute_sql(sql)
    print("-> Result:")
    print(result)
    print("=" * 60)

if __name__ == "__main__":
    # Test queries
    test_q1 = "What was the total traffic (people entered) across all stores?"
    test_q2 = "Which day of the week had the highest total revenue?"
    test_q3 = "How many unique clients did Mobexpert Pipera have at 14:00 (Ora=14) across all days?"
    
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        client = genai.Client()
        ask_database(client, test_q1)
        ask_database(client, test_q2)
        ask_database(client, test_q3)
    except Exception as e:
        print(f"Failed to run due to: {e}. Make sure GEMINI_API_KEY is set in .env")
