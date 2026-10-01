import os
import sys

# Gwarantuje, że Python zawsze widzi pliki z folderu src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import json
import joblib
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from pydantic import BaseModel
from typing import Literal

from document_parser import InvoiceParser
from ml_classifier import ConfidenceRouter
from llm_agent import LLMFallbackClassifier

#schemat danych
class ProcessingReport(BaseModel):
    invoice_number: str
    seller_nip: str
    total_gross: float
    final_category: str
    final_confidence: float
    decision_path: Literal["XGBOOST_FAST_TRACK", "LLM_FALLBACK", "MANUAL_REVIEW", "PARSER_REJECTED"]
    reasoning: str
    raw_text: str


#tworzymy drzewo decyzji
class InvoicePipelineOrchestrator:
    def __init__(
        self, 
        model_name: str = "smart-invoice-pipeline", 
        alias: str = "champion", 
        fallback_pkl: str = "xgboost_pipeline.pkl", 
        model_bundle_path: str | None = None,   # Dodane dla pełnej wstecznej kompatybilności z UI
        llm_api_key: str | None = None
    ):
        self.parser = InvoiceParser()
        self.llm = LLMFallbackClassifier(api_key=llm_api_key)
        
        # Jeśli UI przekazało stary parametr model_bundle_path, traktujemy go jako fallback
        target_fallback = model_bundle_path or fallback_pkl
        
        # 1. Próba załadowania modelu z chmurowego Model Registry MLflow
        try:
            print(f"[MLflow] Pobieranie modelu '{model_name}@{alias}' z rejestru...")
            model_uri = f"models:/{model_name}@{alias}"
            pipeline = mlflow.sklearn.load_model(model_uri)
            
            # Pobieramy plik classes.json powiązany z tą wersją modelu
            client = MlflowClient()
            model_version = client.get_model_version_by_alias(model_name, alias)
            classes_path = mlflow.artifacts.download_artifacts(
                run_id=model_version.run_id, 
                artifact_path="classes.json"
            )
            
            with open(classes_path, "r", encoding="utf-8") as f:
                classes_data = json.load(f)
                classes = np.array(classes_data["classes"])
                
            model_bundle = {
                "pipeline": pipeline,
                "classes": classes
            }
            print(f"[MLflow] Pomyślnie załadowano wersję {model_version.version} (@{alias}) z DagsHub.")
            
        except Exception as err:
            print(f"[Ostrzeżenie] Nie udało się pobrać modelu z MLflow ({err}). Używam lokalnego pliku zapasowego: {target_fallback}")
            model_bundle = joblib.load(target_fallback)
            
        self.router = ConfidenceRouter(model_bundle=model_bundle, confidence_threshold=0.85)
            
    def process_invoice(self, pdf_path: str) -> ProcessingReport:
        """ Metoda sterująca przepływem przez wszsytkie kaskady"""
        try:
            # 1. Parsowanie PDF
            invoice = self.parser.parse(pdf_path=pdf_path)
            
            # 2. Szybka ścieżka ML (XGBoost)
            route = self.router.route_invoice(
                seller_nip=invoice.seller_nip, 
                raw_text=invoice.raw_text
            )
            
            if route["status"] == "AUTO_APPROVED":
                return ProcessingReport(
                    invoice_number = invoice.invoice_number,
                    seller_nip = invoice.seller_nip,
                    total_gross = invoice.total_gross,
                    final_category = route["predicted_category"],
                    final_confidence = route["confidence"],
                    decision_path = "XGBOOST_FAST_TRACK",
                    reasoning = route["action"],
                    raw_text = invoice.raw_text
                )
            else:
                # 3. Warstwa rezerwowa LLM
                prompt = self.llm.build_prompt(
                    raw_text = invoice.raw_text, 
                    xgboost_guess= route["predicted_category"]
                )
               
                try:
                    raw_llm_output = self.llm.call_llm(prompt=prompt)
                    res = self.llm.parse_and_validate(raw_llm_output=raw_llm_output)
                    
                    if res.confidence >= 0.75:
                        return ProcessingReport(
                            invoice_number = invoice.invoice_number,
                            seller_nip = invoice.seller_nip,
                            total_gross = invoice.total_gross,
                            decision_path="LLM_FALLBACK",
                            final_category = res.category,
                            final_confidence= res.confidence,
                            reasoning = res.reasoning,
                            raw_text = invoice.raw_text
                        )
                    else:
                        return ProcessingReport(
                            invoice_number = invoice.invoice_number,
                            seller_nip = invoice.seller_nip,
                            total_gross = invoice.total_gross,
                            decision_path="MANUAL_REVIEW",
                            final_category = res.category,
                            final_confidence= res.confidence,
                            reasoning = f"Niska pewność LLM ({res.confidence * 100:.1f}%). Wymagana weryfikacja człowieka: {res.reasoning}",
                            raw_text = invoice.raw_text
                        )
                
                except Exception as llm_err:
                    # Awaria API / błąd walidacji odpowiedzi LLM -> bezpieczny zrzut do weryfikacji manualnej
                    return ProcessingReport(
                        invoice_number=invoice.invoice_number,
                        seller_nip=invoice.seller_nip,
                        total_gross=invoice.total_gross,
                        decision_path="MANUAL_REVIEW",
                        final_category=route["predicted_category"],
                        final_confidence=route["confidence"],
                        reasoning=f"Awaria fallbacku LLM ({str(llm_err)}). Skierowano do manualnej weryfikacji.",
                        raw_text = invoice.raw_text
                    )        
                
        except Exception as e:
            # Obsługa dokumentów uszkodzonych lub niezgodnych z walidacją
            return ProcessingReport(
                invoice_number="UNKNOWN",
                seller_nip="UNKNOWN",
                total_gross=0.0,
                final_category="UNKNOWN",
                final_confidence=0.0,
                decision_path = "PARSER_REJECTED",
                reasoning=f"Błąd walidacji lub parsowania: {str(e)}"
            )
            
            
import glob
import os

if __name__ == "__main__":
    print("=" * 70)
    print("TEST ORKIESTRATORA Z PRAWDZIWYM API GEMINI")
    print("=" * 70)

    orchestrator = InvoicePipelineOrchestrator(model_bundle_path="xgboost_pipeline.pkl")

    # Testujemy trudną fakturę 044
    pdf_path = "data/raw_pdfs/faktura_044.pdf"
    
    print(f"\n>>> Przetwarzanie: {pdf_path}")
    report = orchestrator.process_invoice(pdf_path=pdf_path)

    print(f"    Numer faktury:   {report.invoice_number}")
    print(f"    NIP sprzedawcy:  {report.seller_nip}")
    print(f"    Kwota brutto:    {report.total_gross:.2f} PLN")
    print(f"    Ścieżka decyzji: [ {report.decision_path} ]")
    print(f"    Kategoria:       {report.final_category} (Pewność: {report.final_confidence * 100:.1f}%)")
    print(f"    Uzasadnienie:    {report.reasoning}")
    print("\n" + "=" * 70)