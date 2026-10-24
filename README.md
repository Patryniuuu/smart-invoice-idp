# 📄 Smart Invoice IDP (Intelligent Document Processing)

**Live Application:** [https://smart-invoice-idp.streamlit.app/](https://smart-invoice-idp.streamlit.app/)

An automated invoice classification and data extraction system built on a hybrid architecture. The project combines the high-speed processing of classical Machine Learning (XGBoost) with the advanced reasoning capabilities of Large Language Models (Google Gemini) to seamlessly handle complex, ambiguous, or damaged documents.

## 🚀 Core Features

* **Hybrid Decision Router (`ConfidenceRouter`):** Utilizes an XGBoost classification algorithm for lightning-fast processing. If the model's confidence falls below a dynamically adjustable threshold (e.g., 85%), the invoice is automatically escalated to the AI Agent.


* **LLM Fallback:** Intelligent document classification using the `google-genai` SDK (Gemini 2.5 Flash) with an exponential backoff retry mechanism for highly unstructured edge cases.


* **Active Learning & Model Registry:** The system continuously learns from human corrections via a Human-in-the-loop queue. After passing strict quality gates (F1-score, Slice Test), the retrained model is automatically registered in a cloud-based MLflow environment (DagsHub) and deployed as the production `@champion`.


* **PDF Extraction & Validation:** Secure document parsing and strict schema enforcement using `pdfplumber` and `Pydantic`.


* **ERP Integration:** Generates clean, standardized CSV exports of automatically approved and human-resolved invoices, omitting technical data for seamless accounting software ingestion.



## 🛠️ Tech Stack

* **Language:** Python 3.11


* **User Interface:** Streamlit


* **Machine Learning:** scikit-learn (1.5.1), XGBoost (2.1.1)


* **MLOps:** MLflow (DagsHub), skops, joblib


* **LLM Integration:** `google-genai` SDK


* **Data Validation:** Pydantic (>=2.0.0), Pandas, Numpy


* **Deployment:** Docker, Docker Compose, Streamlit Community Cloud



## 📂 Project Structure

* `app/main_ui.py` - Main Streamlit interface and application entry point.


* `src/orchestrator.py` - Core pipeline controller managing the cascade from PDF extraction to XGBoost and LLM routing.


* `src/ml_classifier.py` - XGBoost pipeline definition and `ConfidenceRouter` logic.


* `src/llm_agent.py` - AI agent configuration, prompt engineering, and JSON validation.


* `src/train_mlflow.py` - Active learning logic, model retraining, and MLflow registry integration.


* `data/` - Mapped Docker volume for human feedback buffers, dataset archives, and raw PDFs.


* `xgboost_pipeline.pkl` - Local fallback model utilized if the cloud registry is unreachable.



## ⚙️ Local Setup & Execution

1. **Clone the repository:**
```bash
git clone https://github.com/Patryniuuu/smart-invoice-idp.git
cd smart-invoice-idp

```


2. **Environment Configuration:**
Create a `.env` file in the root directory and add your authentication keys (this file is excluded via `.gitignore`):


```toml
MLFLOW_TRACKING_URI="https://dagshub.com/Patryniuuu/smart-invoice-idp.mlflow"
MLFLOW_TRACKING_USERNAME="your_username"
MLFLOW_TRACKING_PASSWORD="your_token"
GEMINI_API_KEY="your_gemini_api_key"

```


3. **Run via Docker Compose:**
Build and launch the `invoice-app` container:


```bash
docker compose up --build

```


The application will be accessible at `http://localhost:8501`.



## 🧪 Testing

The business logic of the decision router and LLM parser is covered by automated unit tests. To run the test suite, execute:

```bash
pytest -v

```

## ☁️ Cloud Deployment

The project is fully optimized for **Streamlit Community Cloud**. It utilizes the cloud-native `Secrets` management (TOML format) to securely store API keys and MLflow credentials without requiring a local `.env` file. The deployment triggers automatically from the `main` branch.

## 📜 License

This project is licensed under the **MIT License**.
Copyright (c) 2026 Patryk Kubik. See the `LICENSE` file for more details.
