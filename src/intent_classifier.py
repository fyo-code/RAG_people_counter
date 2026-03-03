from google import genai
from google.genai import types

# This is our classification taxonomy. We clearly define the rules for each category.
CLASSIFICATION_PROMPT = """
Sunteți "creierul" de rutare al unui chatbot de analiză de retail.
Singura dumneavoastră sarcină este să clasificați întrebarea utilizatorului (care va fi în limba română) într-una din următoarele două categorii stricte.

CATEGORIILE:

1. QUANTITATIVE
- Folosiți aceasta dacă întrebarea solicită un fapt specific, număr, total, medie, clasament, sau o extragere exactă din datele brute.
- Exemple: 
  - "Câți oameni au intrat în Magazinul X astăzi?"
  - "Care au fost veniturile totale luni?"
  - "Care este rata de conversie pentru Mobexpert Pipera?"
  - "Care este ora cu cel mai mare trafic?"
  - "Care a fost rata de conversie medie pe zi de la 01.02 până la 15.02?"

2. ANALYTICAL
- Folosiți aceasta dacă întrebarea întreabă "de ce", cere tendințe complexe, tipare, insight-uri de business sau analiză calitativă care necesită gândire dincolo de simpla adunare a numerelor.
- Exemple:
  - "De ce scade traficul în toate magazinele?"
  - "Ce tipare sezoniere vedem în ratele de conversie?"
  - "Compară performanța magazinului X și Y și explică diferența."

REGULI:
- Trebuie să returnați EXACT UN CUVÂNT: fie QUANTITATIVE, fie ANALYTICAL.
- Nu scrieți nimic altceva. Fără explicații, fără punctuație.
"""

def classify_intent(client: genai.Client, user_question: str) -> str:
    """Takes a user question and classifies it using a fast, cheap model (Flash)."""
    # We use gemini-2.5-flash because classification is a simple task 
    # and requires low latency and low cost.
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_question,
        config=types.GenerateContentConfig(
            system_instruction=CLASSIFICATION_PROMPT,
            temperature=0.0  # Zero temperature for deterministic classification
        )
    )
    
    # Clean up the output to ensure it matches exactly one of our categories
    intent = response.text.strip().upper()
    
    # Safety fallback
    valid_intents = ["QUANTITATIVE", "ANALYTICAL"]
    if intent not in valid_intents:
        # If the LLM somehow outputs a weird string, default to ANALYTICAL
        # since ANALYTICAL can theoretically invoke the SQL pipeline as well in hybrid mode
        print(f"Warning: Unexpected intent received '{intent}'. Defaulting to ANALYTICAL.")
        return "ANALYTICAL"
        
    return intent

if __name__ == "__main__":
    # Our custom test set to validate accuracy
    test_questions = [
        # Quantitative
        ("What was the footfall for Mobexpert Pipera at 15:00?", "QUANTITATIVE"),
        ("How much money was refunded on Monday?", "QUANTITATIVE"),
        
        # Analytical
        ("Why did the conversion rate drop on Friday compared to Thursday?", "ANALYTICAL"),
        ("What is the general trend in average ticket size over the month?", "ANALYTICAL"),
        
        # Meta
        ("What does the column ZiLuna mean?", "META"),
        ("Explain how we decide if a client is considered unique.", "META"),
        
        # Ambiguous / Edge cases
        ("Which store is doing the best right now?", "ANALYTICAL"), # Requires defining "best" and comparing
        ("Show me the total sales.", "QUANTITATIVE") 
    ]
    
    print("Running Intent Classifier Tests...\n")
    correct = 0
    
    for q, expected in test_questions:
        predicted = classify_intent(q)
        status = "✅ PASS" if predicted == expected else f"❌ FAIL (Expected {expected})"
        print(f"Q: '{q}'\n-> Predicted: {predicted} | {status}\n")
        
        if predicted == expected:
            correct += 1
            
    print(f"Score: {correct}/{len(test_questions)} ({correct/len(test_questions)*100:.0f}%)")
