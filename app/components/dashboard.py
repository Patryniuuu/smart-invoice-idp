import streamlit as st
import pandas as pd
import os
from datetime import datetime

def save_feedback(invoice_number, correct_category, seller_nip, raw_text):
    """Zapisuje ręczną korektę do pliku CSV (pętla sprzężenia zwrotnego dla ML)."""
    feedback_file = "data/human_feedback.csv"
    
    os.makedirs("data", exist_ok=True)
    
    new_data = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "invoice_number": invoice_number,
        "seller_nip": seller_nip,       # <-- NOWE POLE (cecha kategoryczna)
        "raw_text": raw_text,           # <-- NOWE POLE (cecha tekstowa do TF-IDF)
        "category": correct_category
    }])
    
    if not os.path.exists(feedback_file):
        new_data.to_csv(feedback_file, index=False)
    else:
        new_data.to_csv(feedback_file, mode='a', header=False, index=False)

def render_report(report):
    """Renderuje kokpit analityczny na podstawie obiektu ProcessingReport."""
    
    st.subheader("📊 Wyniki Analizy Dokumentu")
    
    # 1. Karta Metryk
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Numer faktury", value=report.invoice_number)
    col2.metric(label="NIP Sprzedawcy", value=report.seller_nip)
    col3.metric(label="Kwota Brutto", value=f"{report.total_gross:.2f} PLN")
        
    st.markdown("---")
    
    # 2. Status Kaskady
    path = report.decision_path
    if path == "XGBOOST_FAST_TRACK":
        st.success("🟢 XGBOOST FAST-TRACK: Zaksięgowano automatycznie (0 kosztów API).")
    elif path == "LLM_FALLBACK":
        st.info("🔵 LLM FALLBACK: Przeanalizowano i zatwierdzono przez Agenta AI.")
    elif path == "MANUAL_REVIEW":
        st.warning("🟡 MANUAL REVIEW: Zbyt niska pewność systemu. Wymagana akceptacja.")
    elif path == "PARSER_REJECTED":
        st.error("🔴 PARSER REJECTED: Dokument uszkodzony lub brakuje kluczowych danych.")
        
    st.markdown("---")

    # 3. Kategoria i Pewność
    st.markdown(f"### Wykryta kategoria: **`{report.final_category}`**")
    conf_value = max(0.0, min(1.0, report.final_confidence))
    st.progress(conf_value, text=f"Pewność systemu: {conf_value * 100:.1f}%")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. Ścieżka Audytu
    st.markdown("**Uzasadnienie biznesowe:**")
    st.code(report.reasoning, language="text")

    # Weryfikacja manualna dla pojedynczej analizy
    if path in ["MANUAL_REVIEW", "LLM_FALLBACK"]:
        st.markdown("---")
        st.markdown("### 🧑‍💻 Weryfikacja Manualna")
        st.caption("Ten dokument wymaga nadzoru. Potwierdź lub zmień kategorię, aby douczyć model ML.")
        
        categories = ["OFFICE_SUPPLIES", "IT_HARDWARE", "IT_SERVICES", "TRAVEL_FLEET"]
        default_index = categories.index(report.final_category) if report.final_category in categories else 0
        
        with st.form(key=f"feedback_form_{report.invoice_number}"):
            selected_category = st.selectbox(
                "Poprawna kategoria kosztowa:", 
                options=categories,
                index=default_index
            )
            
            submit_btn = st.form_submit_button("✅ Zatwierdź i zapisz w bazie wiedzy", type="primary")
            
            if submit_btn:
                save_feedback(invoice_number=report.invoice_number, 
                              correct_category = selected_category,
                              seller_nip=report.seller_nip,
                              raw_text=report.raw_text)
                st.success(f"Zapisano korektę: {selected_category}! Decyzja trafiła do bazy wiedzy.")