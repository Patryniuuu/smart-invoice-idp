import pytest
import numpy as np
from unittest.mock import MagicMock
import sys
import os

sys.path.append(os.path.abspath("src"))
from ml_classifier import ConfidenceRouter

@pytest.fixture
def mock_router():
    """Tworzy instancję ConfidenceRouter z zamockowanym modelem ML."""
    mock_pipeline = MagicMock()
    mock_bundle = {
        "pipeline": mock_pipeline,
        "classes": np.array(["Biuro", "Paliwo", "IT"])
    }
    router = ConfidenceRouter(model_bundle=mock_bundle, confidence_threshold=0.85)
    return router, mock_pipeline

def test_high_confidence_routes_to_ml(mock_router):
    router, mock_pipeline = mock_router
    # Mock zwraca 95% pewności dla klasy "Biuro"
    mock_pipeline.predict_proba.return_value = np.array([[0.95, 0.03, 0.02]])
    
    result = router.route_invoice(seller_nip="1234567890", raw_text="Artykuly biurowe")
    
    assert result["action"] == "Księgowanie automatyczne w ERP."
    assert result["predicted_category"] == "Biuro"
    assert result["confidence"] >= 0.85

def test_low_confidence_routes_to_fallback(mock_router):
    router, mock_pipeline = mock_router
    # Mock zwraca 60% pewności (poniżej progu 85%)
    mock_pipeline.predict_proba.return_value = np.array([[0.60, 0.25, 0.15]])
    
    result = router.route_invoice(seller_nip="9999999999", raw_text="Nieznana usługa")
    
    assert result["action"] == "Wymagana weryfikacja (przekierowanie do LLM / człowieka)."
    assert result["confidence"] < 0.85