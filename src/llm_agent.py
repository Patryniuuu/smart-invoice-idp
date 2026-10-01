import json
import re
from typing import Literal
from pydantic import BaseModel, Field, ValidationError
from google import genai
import os
from dotenv import load_dotenv

import time
import logging

logger = logging.getLogger(__name__)


# Schemat danych LLMa w Pydanticu
# # Literal wymusza, że kategoria MUSI być dokładnie jedną z tych czterech wartości:
AllowedCategory = Literal["IT_HARDWARE", "IT_SERVICES", "OFFICE_SUPPLIES", "TRAVEL_FLEET"]

class LLMClassificationResult(BaseModel):
    """Ścisły schemat odpowiedzi, jakiego wymagamy od LLMa."""
    
    category: AllowedCategory = Field(
        description="Wybrana kategoria kosztowa faktury."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="Pewność decyzji w skali od 0.0 do 1.0."
    )
    reasoning: str = Field(
        description="Krótkie uzasadnienie biznesowe decyzji (maksymalnie 1-2 zdania)."
    )


# =====================================================================
# 2. SILNIK OBSŁUGI FALLBACKU (LLMFallbackClassifier)
# =====================================================================
class LLMFallbackClassifier:
    """Odpowiada za przygotowanie zapytania, wywołanie LLM i walidację wyniku."""

    def __init__(self, api_key: str | None = None):
        # 1. Wczytujemy zmienne z pliku .env do środowiska systemu
        load_dotenv()
        
        # 2. Bierzemy klucz przekazany wprost LUB wyciągamy go z .env
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("Nie znaleziono klucza GEMINI_API_KEY w pliku .env ani jako argumentu!")
        
        # 3. Klienta GenAI możemy zainicjalizować raz dla całej klasy
        self.client = genai.Client(api_key=self.api_key)
        
        # Dopuszczalne kategorie do wstrzyknięcia do promptu
        self.categories_description = """
        - IT_HARDWARE: Sprzęt komputerowy, monitory, laptopy, akcesoria, kable, części PC.
        - IT_SERVICES: Chmura (AWS, Azure), licencje oprogramowania, domeny, hosting, wsparcie IT.
        - OFFICE_SUPPLIES: Artykuły biurowe, papier ksero, tonery, kawa, środki czystości.
        - TRAVEL_FLEET: Paliwo, bilety PKP/lotnicze, hotele, parkingi, opłaty autostradowe.
        """
        

    def build_prompt(self, raw_text: str, xgboost_guess: str) -> str:
        """
        Budujemy system prompta dla agenta
        """
        prompt = f"""
        Jesteś ekspertem księgowym analizującym trudne faktury.
        Twoim zadaniem jest przypisanie faktury do JEDNEJ z poniższych kategorii kosztowych:
        {self.categories_description}

        Kontekst:
        Model XGBoost zasugerował kategorię: {xgboost_guess}, ale miał niską pewność.

        Treść faktury:
        \"\"\"
        {raw_text}
        \"\"\"

        Odpowiedz WYŁĄCZNIE czystym obiektem JSON o polach:
        {{
        "category": "...",
        "confidence": 0.0-1.0,
        "reasoning": "..."
        }}
        """
        return prompt.strip()

    def clean_json_response(self, raw_response: str) -> str:
        """Wyciąga czysty blok JSON niezależnie od komentarzy LLM wokół niego."""
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if not match:
            raise ValueError(f"W odpowiedzi LLM nie znaleziono obiektu JSON: {raw_response}")
        return match.group(0).strip()
    
    def parse_and_validate(self, raw_llm_output: str) -> LLMClassificationResult:
        """
        Parsuje i waliduje output LLMa
        """
        clean = self.clean_json_response(raw_response=raw_llm_output)
        res = LLMClassificationResult.model_validate_json(clean)
        return res

    def mock_llm_call(self, prompt: str) -> str:
        """
        Symulator odpowiedzi LLM (użyteczny do testów jednostkowych bez zużywania API).
        Zwraca przykładowy tekst, jaki oddałby model językowy.
        """
        # Celowo symulujemy odpowiedź opakowaną w markdown, jak robi to większość LLM-ów:
        return """```json
        {
        "category": "TRAVEL_FLEET",
        "confidence": 0.95,
        "reasoning": "Faktura zawiera pozycję 'Olej napędowy Verva' oraz dane stacji paliw Orlen, co jednoznacznie wskazuje na koszty floty/podróży."
        }
        ```"""
    
    
    def call_llm(self, prompt: str, max_retries: int = 3, base_delay: float = 2.0) -> str:
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Wszystkie {max_retries} próby wywołania LLM nie powiodły się: {e}")
                    raise e
                
                # Wzór na exponential backoff: 2s, 4s, 8s...
                sleep_time = base_delay * (2 ** attempt)
                logger.warning(
                    f"Błąd LLM ({e}). Próba {attempt + 1}/{max_retries} nieudana. "
                    f"Czekam {sleep_time}s przed ponowieniem..."
                )
                time.sleep(sleep_time)
            
def run_test():
    classifier = LLMFallbackClassifier()
    
    # 1. Test symulacji standardowej
    prompt = classifier.build_prompt(
        raw_text="Faktura za paliwo PB95 ze stacji PKN Orlen", 
        xgboost_guess="TRAVEL_FLEET"
    )
    raw_output = classifier.mock_llm_call(prompt)
    result = classifier.parse_and_validate(raw_output)
    
    print("--- TEST MOCK LLM ---")
    print(f"Kategoria:   {result.category}")
    print(f"Pewność:     {result.confidence}")
    print(f"Wyjaśnienie: {result.reasoning}\n")

    # 2. Test odporności na 'gadatliwy' model (tekst przed i po JSON-ie)
    dirty_llm_response = """
    Cześć! Przeanalizowałem fakturę i oto wynik:
    ```json
    {
      "category": "OFFICE_SUPPLIES",
      "confidence": 0.88,
      "reasoning": "Zakup papieru biurowego i segregatorów w hurtowni Biuromax."
    }
    ```
    Mam nadzieję, że pomogłem!
    """
    dirty_result = classifier.parse_and_validate(dirty_llm_response)
    print("--- TEST ODPORNOŚCI (BRUDNY JSON) ---")
    print(f"Kategoria:   {dirty_result.category}")
    print(f"Pewność:     {dirty_result.confidence}")
    print(f"Wyjaśnienie: {dirty_result.reasoning}")

if __name__ == "__main__":
    run_test()