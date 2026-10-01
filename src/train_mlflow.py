import pandas as pd
import numpy as np
import os
import joblib
import mlflow
from datetime import datetime
import mlflow.xgboost
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from ml_classifier import build_pipeline
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

load_dotenv()

def load_data(csv_path: str = "data/invoices_dataset.csv") -> pd.DataFrame:
    data = pd.read_csv(csv_path)
    print(f"Załadowano dane o wymiarach: {data.shape}")
    print(data["category"].value_counts())
    return data

#run gdzie trenuje baseline model
def train_baseline():
    mlflow.set_experiment("smart-invoice-classifier")
    data = load_data()
    
    X = data[["seller_nip", "raw_text"]]
    y = data["category"]
    
    #XGBoost potrzebuje miec zakodowane klasy zatem
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y) #koduje klasy
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded)

    pipeline = build_pipeline()
    
    with mlflow.start_run(run_name="baseline_model"):
        fitted_model = pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        accuracy = accuracy_score(y_true=y_test, y_pred=y_pred)
        precision, recall, fscore, _ = precision_recall_fscore_support(y_true=y_test, y_pred=y_pred, average="macro")
        mlflow.log_metrics({"accuracy": accuracy,
                            "precision": precision,
                            "recall": recall,
                            "f1_macro": fscore})
        
        #dodaje zaufane typy zeby nie rzucilo bledem
        trusted_types = [
            "sklearn.compose._column_transformer._RemainderColsList",
            "xgboost.core.Booster",
            "xgboost.sklearn.XGBClassifier",
        ]

        # Zapisujemy mapowanie klas do artefaktów runu
        mlflow.log_dict({"classes": label_encoder.classes_.tolist()}, "classes.json")
        
        mlflow.sklearn.log_model(
            sk_model=fitted_model,
            name="invoice_pipeline",
            skops_trusted_types=trusted_types
        )

#run gdzie trenuje skorygowany model, w MLOpsie wazna zasada jest ze testujemy model NA TYM SAMYM ZESTAWIE DANYCH tzw. golden set, zeby moc go rzetelnie porownac z baseline modelem
def train_active_learning():
    mlflow.set_experiment("smart-invoice-classifier")
    
    feedback_path = "data/human_feedback.csv"
    if not os.path.exists(feedback_path) or os.path.getsize(feedback_path) == 0:
        return {"status": "EMPTY", "message": "Brak pliku poprawek."}
    
    human_fb = pd.read_csv(feedback_path)
    
    if len(human_fb) == 0:
        return {"status": "EMPTY", "message": "Brak nowych poprawek w buforze do retreningu."}
    
    required_cols = {"seller_nip", "raw_text", "category"} #sprawdzamy czy human_fb ma wymagane kolumny
    if not required_cols.issubset(human_fb.columns):
        msg = f"Błąd schematu kolumn! Oczekiwano: {required_cols}, otrzymano: {list(human_fb.columns)}"
        return {"status": "ERROR", "message": msg}
        
    base = load_data()
    pipeline = build_pipeline()
    
    X = base[["seller_nip", "raw_text"]].copy()
    X["seller_nip"] = X["seller_nip"].astype(str) #czasem seller nip jest intem czasem obiektem i pozniej one hot encoding wariuje
    y = base["category"]
    
    #XGBoost potrzebuje miec zakodowane klasy zatem
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y) #koduje klasy
    
    # 3. SPRAWDZENIE CZY KATEGORIE Z FEEDBACKU SĄ ZNANE
    y_fb = human_fb["category"]
    unknown_classes = set(y_fb) - set(label_encoder.classes_)
    if unknown_classes:
        return {
            "status": "ERROR", 
            "message": f"Feedback zawiera nieznane kategorie: {unknown_classes}"
        }
        
    X_train_base, X_test, y_train_base, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded)
    
    X_fb = human_fb[["seller_nip", "raw_text"]].copy()
    X_fb["seller_nip"] = X_fb["seller_nip"].astype(str)
    
    X_train_full = pd.concat([X_train_base, X_fb], ignore_index=True)
    
    #poki co Xtrain_full ma 820 wierszy a y_train_base 800, musze dolaczyc jeszcze pozostale z human_fb
    y_fb_encoded = label_encoder.transform(y_fb)
    y_train_full = np.concatenate([y_train_base, y_fb_encoded]) 
    #teraz y_train_full ma 820 wierszy
    
    weights_base = [1.0] * len(X_train_base)    # lista 800 jedynek
    weights_fb = [4.0] * len(human_fb)          # lista 20 czwórek
    sample_weights = weights_base + weights_fb   # złączona lista 820 wag   
    
    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    with mlflow.start_run(run_name=f"active_learning_{run_timestamp}"):
        MIN_F1_THRESHOLD = 0.98
        MIN_SLICE_THRESHOLD = 1.0  # Wymagamy 100% poprawności na poprawkach człowieka
        
        fitted_model = pipeline.fit(
            X_train_full, 
            y_train_full, 
            classifier__sample_weight=sample_weights
        )
        
        y_pred = pipeline.predict(X_test)
        accuracy = accuracy_score(y_true=y_test, y_pred=y_pred)
        precision, recall, fscore, _ = precision_recall_fscore_support(y_true=y_test, y_pred=y_pred, average="macro")
        
        mlflow.log_metrics({
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_macro": fscore
        })
        
        # 2. SLICE TEST
        y_fb_pred = pipeline.predict(X_fb)
        slice_accuracy = accuracy_score(y_true=y_fb_encoded, y_pred=y_fb_pred)
        mlflow.log_metric("slice_feedback_accuracy", slice_accuracy)
        print(f"Slice Test (Feedback Accuracy): {slice_accuracy * 100:.1f}%")
        
        # Zaufane typy dla skops
        trusted_types = [
            "sklearn.compose._column_transformer._RemainderColsList",
            "xgboost.core.Booster",
            "xgboost.sklearn.XGBClassifier",
        ]

        # Zapisujemy mapowanie klas do artefaktów runu
        mlflow.log_dict({"classes": label_encoder.classes_.tolist()}, "classes.json")
    
        # 3. SPRAWDZENIE BRAMKI JAKOŚCIOWEJ
        if fscore >= MIN_F1_THRESHOLD and slice_accuracy >= MIN_SLICE_THRESHOLD:
            mlflow.set_tag("quality_gate", "PASSED")
            
            # --- BEZPOŚREDNIA REJESTRACJA W MODEL REGISTRY ---
            model_info = mlflow.sklearn.log_model(
                sk_model=fitted_model,
                name="invoice_pipeline",
                registered_model_name="smart-invoice-pipeline",
                skops_trusted_types=trusted_types
            )
            
            new_version = model_info.registered_model_version
            
            # Przypisanie aliasu champion
            client = MlflowClient()
            client.set_registered_model_alias(
                name="smart-invoice-pipeline",
                alias="champion",
                version=str(new_version)
            )
            print(f"✅ Bramka zaliczona! Nowy model (Wersja {new_version}) otrzymał alias @champion!")
            
            # Lokalna kopia bezpieczeństwa (jako fallback offline)
            model_path = "xgboost_pipeline.pkl"
            model_artifact = {
                "pipeline": fitted_model,
                "classes": label_encoder.classes_
            }
            joblib.dump(model_artifact, model_path)
            
            # KROK A: Dopisz poprawki do bazy głównej
            feedback_to_append = human_fb.copy()
            feedback_to_append["filename"] = feedback_to_append["invoice_number"].apply(
                lambda x: f"feedback_{x.replace('/', '_')}.pdf"
            )
            base_schema = ["filename", "seller_nip", "raw_text", "category"]
            feedback_to_append = feedback_to_append[base_schema]
            feedback_to_append.to_csv("data/invoices_dataset.csv", mode="a", header=False, index=False)
            print(f"Dopisano {len(feedback_to_append)} wierszy do bazy invoices_dataset.csv.")
            
            # KROK B: Utwórz kopię archiwalną
            archive_dir = "data/archive"
            os.makedirs(archive_dir, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = os.path.join(archive_dir, f"feedback_{timestamp_str}.csv")
            human_fb.to_csv(archive_path, index=False)
            print(f"Zarchiwizowano bufor poprawek w: {archive_path}")

            # KROK C: Wyczyść bufor roboczy
            empty_df = pd.DataFrame(columns=human_fb.columns)
            empty_df.to_csv(feedback_path, index=False)
            print(f"Zresetowano plik roboczy {feedback_path}.")
            
            return {
                "status": "SUCCESS",
                "message": f"Nowy model (Wersja {new_version}) zaliczył testy i został wdrożony jako @champion.",
                "f1_macro": fscore,
                "slice_accuracy": slice_accuracy,
                "archived_rows": len(feedback_to_append)
            }
        else:
            mlflow.set_tag("quality_gate", "FAILED")
            print("⚠️️ Model nie przeszedł bramki jakościowej. Pozostajemy przy dotychczasowym @champion.")
            return {
                "status": "FAILED",
                "message": "Nowy model nie spełnił kryteriów jakości (zostajemy przy poprzedniej wersji).",
                "f1_macro": fscore,
                "slice_accuracy": slice_accuracy
            }

if __name__ == "__main__":
    train_baseline()