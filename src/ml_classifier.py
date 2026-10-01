import os
import pandas as pd
# Importujemy nasz gotowy parser z poprzedniego modułu
from document_parser import InvoiceParser

def build_dataset(csv_path: str = "data/dataset_labels.csv", pdf_dir: str = "data/raw_pdfs") -> pd.DataFrame:
    """
    Agreguje dane do postaci tabelarycznej (Pandas DataFrame).
    Zwraca kolumny: ['filename', 'seller_nip', 'raw_text', 'category']
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Brak pliku z etykietami: {csv_path}")

    # Wczytujemy plik CSV z etykietami (nasze Ground Truth)
    df_labels = pd.read_csv(csv_path)
    
    parser = InvoiceParser()
    dataset_records = []

    print(f"Budowanie zbioru danych ML z {len(df_labels)} rekordów...")

    for _, row in df_labels.iterrows(): #iterrows() zwraca tuple (index, row), stad mam _ dla index i row dla row
        filename = row["filename"]
        category = row["category"] # To nasz Target (Y)
        pdf_path = os.path.join(pdf_dir, filename)

        try:
            # Używamy naszego parsera do wyciągnięcia NIP-u i pełnego tekstu
            parsed_invoice = parser.parse(pdf_path)
            
            dataset_records.append({
                "filename": filename,
                "seller_nip": parsed_invoice.seller_nip,  # Cecha (X1)
                "raw_text": parsed_invoice.raw_text,      # Cecha (X2)
                "category": category                      # Cel (Y)
            })
        except Exception as e:
            # W świecie Data Science zawsze zakłada się, że ułamek danych będzie uszkodzony
            print(f"[Ostrzeżenie] Pominięto {filename} ze względu na błąd parsowania: {e}")

    df = pd.DataFrame(dataset_records)
    print(f"Zbudowano DataFrame o rozmiarze: {df.shape}")
    return df


from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

def build_pipeline() -> Pipeline:
    """
    Buduje i zwraca potok ML: transformacja danych + klasyfikator XGBoost.
    """
    
    # 1. Definiujemy, jak chcemy przetwarzać poszczególne kolumny
    preprocessor = ColumnTransformer(
        transformers=[     #("nazwa_własna", Narzędzie(), "nazwa_kolumny_w_tabeli"), przerabia dfa zeby byly liczby (bo xgboost operuje tylko na liczbach)
            (
                "text_features", 
                TfidfVectorizer(max_features=500, ngram_range=(1, 2)), 
                "raw_text"  # Wektorujemy tekst. ngram_range=(1,2) złapie m.in. zbitki typu "Olej napędowy", ngram_range = (min_liczba_slow_brana_pod_uwage, max_liczba_slow_brana_pod_uwage)
            ),
            (
                "nip_features", 
                OneHotEncoder(handle_unknown="ignore"), 
                ["seller_nip"]  # Tworzymy flagi 0/1 dla znanych NIP-ów
            )
        ]
    )

    # 2. Łączymy transformator i model w jeden spójny rurociąg (Pipeline)
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", XGBClassifier(
            objective="multi:softprob",  # Klasyfikacja wieloklasowa zwracająca prawdopodobieństwa
            eval_metric="mlogloss",
            random_state=42
        ))
    ])

    return pipeline


from sklearn.model_selection import train_test_split
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

def train_model(df: pd.DataFrame, pipeline: Pipeline) -> Pipeline:
    """
    Dzieli dane, trenuje potok (Pipeline) i zwraca gotowy model.
    """
    print("Rozpoczynam przygotowanie danych do treningu...")

    # ZADANIE 1: Wyodrębnij zmienne objaśniające (X) i zmienną docelową (y)
    # X powinno zawierać tylko kolumny, których używa preprocessor ("seller_nip", "raw_text")
    # y to nasza etykieta docelowa ("category")
    X = df[["seller_nip", "raw_text"]]
    y = df["category"]

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)  # Zamienia napisy na [0, 1, 2, 3]
    
    # ZADANIE 2: Podziel dane na zbiór treningowy (80%) i testowy (20%)
    # Użyj funkcji train_test_split. Pamiętaj o dodaniu parametru random_state=42,
    # aby przy każdym uruchomieniu podział był dokładnie taki sam.
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded) #stratify odpowiada za to aby byly zachowane proprocje w danych treningowych i testowych 

    print(f"Dane podzielone. Rozmiar zbioru treningowego: {len(X_train)} wierszy.")
    print("Rozpoczynam trening modelu XGBoost (TF-IDF + OneHot -> XGB)...")

    # ZADANIE 3: Wytrenuj rurociąg na danych treningowych
    pipeline = pipeline.fit(X_train,y_train)

    # ZADANIE 4: Oceń model na danych testowych (tzw. "egzamin")
    # Użyj metody .score() na swoim pipeline, przekazując dane testowe, aby uzyskać dokładność (accuracy)
    accuracy = pipeline.score(X_test, y_test)
    
    print(f"Trening zakończony! Dokładność na zbiorze testowym: {accuracy * 100:.2f}%")

    # Zwracamy gotowy, naładowany wiedzą rurociąg
    return pipeline, label_encoder

import numpy as np
import pandas as pd

class ConfidenceRouter:
    """Odpowiada za decydowanie, czy predykcja XGBoost jest wystarczająco pewna."""

    def __init__(self, model_bundle: dict, confidence_threshold: float = 0.85):
        # model_bundle to słownik, który zapisaliśmy: {"pipeline": ..., "classes": ...}
        self.pipeline = model_bundle["pipeline"]
        self.classes = model_bundle["classes"]
        self.threshold = confidence_threshold

    def route_invoice(self, seller_nip: str, raw_text: str) -> dict:
        """
        Ocenia fakturę i zwraca decyzję: AUTO_APPROVED lub ESCALATE_TO_LLM.
        """

        # ZADANIE 1: Zbuduj DataFrame z jednym wierszem
        # Pipeline wymaga dokładnie takich samych kolumn jak przy treningu: "seller_nip" oraz "raw_text"
        input_df = pd.DataFrame([{"seller_nip": seller_nip, "raw_text": raw_text}])
        
        # ZADANIE 2: Pobierz rozkład prawdopodobieństw z pipeline
        # Użyj metody predict_proba() na self.pipeline. Pamiętaj, że zwraca ona tablicę 2D:
        # np. [[0.1, 0.85, 0.03, 0.02]] - interesuje Cię pierwszy wiersz [0]
        probabilities = self.pipeline.predict_proba(input_df)[0]

        # ZADANIE 3: Wyznacz zwycięską klasę i jej pewność
        best_idx = np.argmax(probabilities)
        confidence = probabilities[best_idx]                   # Wartość prawdopodobieństwa (od 0.0 do 1.0)
        predicted_category = self.classes[best_idx]            # Odczytaj nazwę z self.classes za pomocą best_idx

        # ZADANIE 4: Logika routingu (warunek progowy)
        # Jeśli confidence >= self.threshold -> status "AUTO_APPROVED"
        # W przeciwnym razie -> status "ESCALATE_TO_LLM"
        if confidence >= self.threshold:
            status = "AUTO_APPROVED"
            action = "Księgowanie automatyczne w ERP."
        else:
            status = "ESCALATE_TO_LLM"
            action = "Wymagana weryfikacja (przekierowanie do LLM / człowieka)."

        # Zwracamy czytelny słownik z werdyktem
        return {
            "predicted_category": predicted_category,
            "confidence": round(float(confidence), 4),
            "status": status,
            "action": action
        }



import joblib  # Wbudowana w scikit-learn biblioteka do zapisu modeli

def main():
    # 1. Złożenie surowych PDF-ów i CSV w tabelę Pandas
    df = build_dataset()
    
    # 2. Budowa i trening rurociągu ML
    pipeline = build_pipeline()
    trained_pipeline, label_encoder = train_model(df, pipeline)
    
    # 3. Zapisanie modelu i etykiet klas do pliku
    model_path = "xgboost_pipeline.pkl"
    model_artifact = {
        "pipeline": trained_pipeline,
        "classes": label_encoder.classes_
    }
    joblib.dump(model_artifact, model_path)
    print(f"Sukces! Gotowy model zapisano na dysku jako: {model_path}\n")

    # ==========================================
    # TEST ROUTERA PEWNOŚCI (CONFIDENCE ROUTER)
    # ==========================================
    print("=" * 60)
    print("START TESTÓW ROUTERA PEWNOŚCI (Próg akceptacji: 85%)")
    print("=" * 60)

    router = ConfidenceRouter(model_bundle=model_artifact, confidence_threshold=0.85)

    test_cases = [
        {
            "nazwa_testu": "Przypadek 1: Znany dostawca paliwa (Orlen)",
            "seller_nip": "5261040828",
            "raw_text": "Faktura VAT: FV/2026/01. Sprzedawca: Orlen Paliwa Sp. z o.o. Pozycja: Olej napędowy Verva. Suma: 350 PLN"
        },
        {
            "nazwa_testu": "Przypadek 2: Znany dostawca IT (Dell)",
            "seller_nip": "5213456789",
            "raw_text": "Faktura VAT: FV/2026/99. Sprzedawca: Dell Polska Sp. z o.o. Pozycja: Monitor Dell 27 cali oraz Klawiatura. DO ZAPŁATY: 2400 PLN"
        },
        {
            "nazwa_testu": "Przypadek 3: Nowy, nieznany NIP + mylący opis (Cold Start / Szum)",
            "seller_nip": "9998887766",
            "raw_text": "Faktura VAT: FV/2026/777. Sprzedawca: Usługi Ogólne Jan Kowalski. Pozycja: Refaktura kosztów projektu i opłata manipulacyjna"
        }
    ]

    for tc in test_cases:
        result = router.route_invoice(seller_nip=tc["seller_nip"], raw_text=tc["raw_text"])
        print(f"\n{tc['nazwa_testu']}")
        print(f"  -> Wykryta kategoria: {result['predicted_category']}")
        print(f"  -> Pewność modelu:     {result['confidence'] * 100:.2f}%")
        print(f"  -> Status decyzyjny:   {result['status']}")
        print(f"  -> Akcja:              {result['action']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()