"""Quick test to validate each Gemini model."""
import os
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"]

PROMPT = 'Analiza el texto: "El curso estuvo excelente". Responde SOLO con JSON: {"aspectos": [{"aspecto_oficial": "Contenido", "sentimiento": "Positivo"}]}'

for model_name in MODELS:
    print(f"\n--- Testing {model_name} ---")
    try:
        model = genai.GenerativeModel(
            model_name,
            system_instruction="Eres un experto en ABSA. Responde solo en JSON valido."
        )
        resp = model.generate_content(
            PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=512,
            )
        )
        print(f"  ✓ SUCCESS")
        print(f"  Response: {resp.text[:200]}")
        print(f"  Tokens: prompt={resp.usage_metadata.prompt_token_count}, completion={resp.usage_metadata.candidates_token_count}")
    except ValueError as ve:
        print(f"  ✗ ValueError (safety block?): {ve}")
        try:
            print(f"  Prompt feedback: {resp.prompt_feedback}")
            print(f"  Candidates: {resp.candidates}")
        except Exception:
            pass
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e}")
