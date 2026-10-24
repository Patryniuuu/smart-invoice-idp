Przygotowałem dla Ciebie profesjonalny plik **`README.md`**, który idealnie podsumowuje cały nasz projekt, jego architekturę oraz stack technologiczny. Taki dokument będzie świetnie wyglądał w Twoim portfolio na GitHubie.

Oto kompletna treść pliku `README.md` oparta na Twoich plikach źródłowych i wcześniejszych ustaleniach:

---

```markdown
# 📄 Smart Invoice IDP (Intelligent Document Processing)

System do automatycznej klasyfikacji i ekstrakcji danych z faktur oparty na hybrydowym podejściu (Machine Learning + LLM). Projekt łączy szybkość klasycznych modeli ML (XGBoost) z potęgą dużych modeli językowych (Google Gemini) w przypadku skomplikowanych lub niepewnych dokumentów.

## 🚀 Główne funkcjonalności

*   **Hybrydowy Router Decyzyjny (`ConfidenceRouter`):** System wykorzystuje algorytm klasyfikacji XGBoost[cite: 9]. Gdy pewność modelu spada poniżej ustalonego progu, system automatycznie przekierowuje fakturę do analizy.
*   **LLM Fallback:** Awaryjna klasyfikacja dokumentów z wykorzystaniem nowoczesnego API `google-genai` (Google Gemini)[cite: 9].
*   **Active Learning & Model Registry:** System automatycznie uczy się na ludzkich poprawkach. Po przejściu testów jakościowych (F1-score, Slice Test), nowy model jest rejestrowany w chmurowym MLflow (DagsHub) i automatycznie wdrażany jako produkcyjny `@champion`[cite: 9].
*   **Ekstrakcja PDF:** Przetwarzanie i walidacja danych z dokumentów odbywa się przy pomocy bibliotek `pdfplumber` oraz `pydantic`[cite: 9].
*   **Konteneryzacja:** Aplikacja jest w 100% zintegrowana ze środowiskiem Docker[cite: 5]. Posiada gotowy plik `docker-compose.yml` zapewniający łatwe uruchamianie[cite: 4].

## 🛠️ Stack Technologiczny

*   **Język:** Python 3.11[cite: 5]
*   **Interfejs Użytkownika:** Streamlit[cite: 9]
*   **Machine Learning:** scikit-learn (wersja 1.5.1), XGBoost (wersja 2.1.1)[cite: 9]
*   **MLOps:** MLflow (do logowania eksperymentów i Model Registry), skops[cite: 9]
*   **LLM:** SDK `google-genai`[cite: 9]
*   **Testowanie:** Pytest[cite: 9]
*   **Środowisko / Wdrożenie:** Docker[cite: 5], Docker Compose[cite: 4], Streamlit Community Cloud / Hugging Face Spaces.

## 📂 Struktura Projektu (Kluczowe pliki)

*   `src/` - Główny kod źródłowy aplikacji (interfejs, routery, parsery PDF).
*   `tests/` - Skrypty testów jednostkowych (uruchamiane przez bibliotekę `pytest`[cite: 9]).
*   `data/` - Zmontowany wolumen Dockera na zestawy danych, bufor poprawek oraz archiwum[cite: 4].
*   `data/archive/` - Automatyczne kopie zapasowe bufora poprawek po retreningu[cite: 2].
*   `xgboost_pipeline.pkl` - Lokalny plik awaryjny (fallback) montowany do kontenera na wypadek braku łączności z chmurą[cite: 4].
*   `.env` - Plik ze zmiennymi środowiskowymi (ignorowany w repozytorium przez `.gitignore`[cite: 3]).

## ⚙️ Uruchomienie lokalne

1. **Sklonuj repozytorium:**
   ```bash
   git clone [https://github.com/Patryniuuu/smart-invoice-idp.git](https://github.com/Patryniuuu/smart-invoice-idp.git)
   cd smart-invoice-idp

```

2. **Skonfiguruj środowisko:**
Utwórz plik `.env` w głównym katalogu projektu i uzupełnij go swoimi kluczami autoryzacyjnymi:


```toml
MLFLOW_TRACKING_URI="[https://dagshub.com/Patryniuuu/smart-invoice-idp.mlflow](https://dagshub.com/Patryniuuu/smart-invoice-idp.mlflow)"
MLFLOW_TRACKING_USERNAME="twoj_login"
MLFLOW_TRACKING_PASSWORD="twoj_token"
GEMINI_API_KEY="twoj_klucz_gemini"

```


3. **Uruchom system przez Docker Compose:**
Zbuduj i uruchom kontener o nazwie `invoice-app`:


```bash
docker compose up --build

```


Aplikacja automatycznie zmapuje porty i będzie dostępna pod adresem `http://localhost:8501`. Kontener jest skonfigurowany do automatycznego restartu w przypadku błędu (`restart: unless-stopped`).



## 🧪 Testy Jednostkowe

Logika biznesowa routera i bramek decyzyjnych jest pokryta automatycznymi testami jednostkowymi. Aby je uruchomić, użyj polecenia:

```bash
pytest -v

```

(Katalogi pamięci podręcznej testów `.pytest_cache/` nie są śledzone przez system kontroli wersji).

## ☁️ Wdrożenie w chmurze (Deploy)

Projekt jest przystosowany do darmowego wdrażania na dwóch platformach:

1. **Streamlit Community Cloud:** Automatyczny deploy prosto z gałęzi `main`.
2. **Hugging Face Spaces:** Aplikacja zawiera zoptymalizowany pod tym kątem `Dockerfile`, który natywnie uruchamia serwer na porcie `7860` i nasłuchuje na adresie `0.0.0.0`. Wewnątrz kontenera zablokowane jest tworzenie plików bytecode `.pyc` (`PYTHONDONTWRITEBYTECODE=1`) oraz włączone jest natychmiastowe strumieniowanie logów (`PYTHONUNBUFFERED=1`).



## 📜 Licencja

Projekt jest udostępniany na warunkach licencji **MIT**.
Copyright (c) 2026 Patryk Kubik. Szczegóły znajdują się w pliku `LICENSE`.

```

***

Plik jest sformatowany, uwzględnia specyfikę działania portów z Dockera oraz wykorzystanie bibliotek wyszczególnionych w Twoich plikach systemowych. Wystarczy go teraz skopiować, zapisać jako `README.md` w głównym katalogu projektu i wysłać na GitHuba komendami:

```powershell
git add README.md
git commit -m "Add professional README"
git push origin main

```