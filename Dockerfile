# 1. Wybór lekkiego, stabilnego obrazu bazowego Pythona
FROM python:3.11-slim

# 2. Ustawienia środowiska Pythona:
# - PYTHONDONTWRITEBYTECODE: nie śmiecimy plikami .pyc w kontenerze
# - PYTHONUNBUFFERED: logi z print/logging trafiają do konsoli natychmiast bez buforowania
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Ustawienie głównego katalogu roboczego w kontenerze
WORKDIR /app

# 4. Kopiujemy sam plik z bibliotekami (dla Layer Cachingu), zeby nie pobierac za kazda zmiana kodu tego samego requirements.txt
COPY requirements.txt .

# 5. Instalacja zależności bez zapisywania zbędnego cache pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Kopiujemy cały kod projektu do kontenera (.dockerignore odrzuci śmieci)
COPY . .

# 7. Deklaracja portu Streamlita
EXPOSE 7860

# 8. Polecenie startowe aplikacji (nasłuchiwanie na 0.0.0.0 jest kluczowe bo bedziemy deployowac streamlita)
CMD ["streamlit", "run", "app/main_ui.py", "--server.port=7860", "--server.address=0.0.0.0"]