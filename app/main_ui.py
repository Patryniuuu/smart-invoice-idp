import sys
import os
import tempfile
import base64
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# 1. Środowisko i ścieżki importu
load_dotenv()
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
for path in [PROJECT_ROOT, SRC_PATH]:
    if path not in sys.path:
        sys.path.append(path)

from orchestrator import InvoicePipelineOrchestrator
from components.dashboard import save_feedback
from train_mlflow import train_active_learning


# ==========================================
# Inicjalizacja komponentów i stanu sesji
# ==========================================
@st.cache_resource
def get_orchestrator():
    return InvoicePipelineOrchestrator(model_bundle_path="xgboost_pipeline.pkl")

def init_session_state():
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = None
    if 'batch_stats' not in st.session_state:
        st.session_state.batch_stats = None
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

def get_feedback_count() -> int:
    """Zwraca liczbę zebranych ręcznych adnotacji."""
    feedback_file = "data/human_feedback.csv"
    if os.path.exists(feedback_file):
        try:
            df_fb = pd.read_csv(feedback_file)
            return len(df_fb)
        except Exception:
            return 0
    return 0

# ==========================================
# Główny interfejs
# ==========================================
def main():
    st.set_page_config(page_title="Smart Invoice IDP", page_icon="🧾", layout="wide")
    init_session_state()
    orchestrator = get_orchestrator()

    # Panel boczny: Konfiguracja i Active Learning
    with st.sidebar:
        st.header("⚙️ Parametry Potoku")
        
        # Dynamiczny próg pewności
        confidence_threshold = st.slider(
            "Próg akceptacji XGBoost",
            min_value=0.50,
            max_value=0.99,
            value=0.85,
            step=0.01,
            help="Poniżej tej wartości faktura trafia do weryfikacji przez Gemini LLM lub człowieka."
        )
        
        # Synchronizacja progu z routerem w backendzie
        if hasattr(orchestrator, 'router') and hasattr(orchestrator.router, 'confidence_threshold'):
            orchestrator.router.confidence_threshold = confidence_threshold
        elif hasattr(orchestrator, 'confidence_threshold'):
            orchestrator.confidence_threshold = confidence_threshold

        st.markdown("---")
        st.subheader("📡 Status Usług")
        st.write("✅ XGBoost: Załadowany")
        if os.getenv("GEMINI_API_KEY"):
            st.write("✅ Gemini API: Aktywne")
        else:
            st.error("❌ Gemini API: Brak klucza!")

        st.markdown("---")
        st.subheader("🧠 Pętla Active Learning")
        fb_count = get_feedback_count()
        st.metric("Zebrane korekty ludzkie", f"{fb_count} / 20")
        
        # Przycisk aktywny zawsze, gdy jest cokolwiek w buforze, 
        # ale z wyróżnieniem, gdy przekroczy 20 próbek
        can_retrain = fb_count > 0
        
        if fb_count >= 20:
            st.success("Zebrano optymalną partię danych do bezpiecznego dotrenowania!")
        elif fb_count > 0:
            st.caption(f"Bufor zawiera {fb_count} korekt. Zalecane: minimum 20.")
        else:
            st.caption("Zbierz korekty w kolejce akceptacji, aby odblokować retrening.")

        if st.button("🔄 Uruchom retrening modelu", disabled=not can_retrain, use_container_width=True):
            with st.spinner("Trenowanie i ewaluacja modelu w DagsHub..."):
                result = train_active_learning()
                
            status = result.get("status")
            
            if status == "SUCCESS":
                st.success(f"✅ {result['message']}")
                st.write(f"• **F1 Golden:** {result['f1_macro']:.4f}")
                st.write(f"• **Slice Accuracy:** {result['slice_accuracy'] * 100:.1f}%")
                
                # 1. Kluczowe: czyszczenie pamięci podręcznej Streamlita
                st.cache_resource.clear()
                
                # 2. Przeładowanie stanu interfejsu (licznik wróci do 0/20)
                st.rerun()
                
            elif status == "FAILED":
                st.error(f"❌ {result['message']}")
                st.write(f"• F1: {result.get('f1_macro', 0):.4f} | Slice: {result.get('slice_accuracy', 0):.2f}")
                
            elif status == "EMPTY":
                st.info(f"ℹ️ {result['message']}")
                
            elif status == "ERROR":
                st.error(f"⚠️ {result['message']}")
    # Główny obszar roboczy (Zunifikowany)
    st.title("🧾 Smart Invoice IDP - Panel Przetwarzania")
    st.markdown("Wgraj jedną lub wiele faktur PDF. System przetworzy je kaskadowo z uwzględnieniem wybranego progu pewności.")

    # Układ dwukolumnowy: Uploader oraz Przycisk czyszczenia
    col_upload, col_clear = st.columns([5, 1])

    with col_upload:
        uploaded_files = st.file_uploader(
            "Przeciągnij pliki PDF", 
            type=["pdf"], 
            accept_multiple_files=True, 
            key=f"uploader_{st.session_state.uploader_key}"
        )

    with col_clear:
        # Odstęp wyrównujący przycisk z polem wgrywania plików
        st.write("")
        st.write("")
        if st.button("🗑️ Wyczyść pliki", use_container_width=True):
            st.session_state.uploader_key += 1
            st.session_state.batch_results = None
            st.session_state.batch_stats = None
            st.rerun()

    if uploaded_files:
        if st.button("🚀 Rozpocznij przetwarzanie", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            stats = {
                "XGBOOST_FAST_TRACK": 0, 
                "LLM_FALLBACK": 0, 
                "MANUAL_REVIEW": 0, 
                "PARSER_REJECTED": 0, 
                "RESOLVED_BY_HUMAN": 0
            }
            total_files = len(uploaded_files)

            for idx, file in enumerate(uploaded_files):
                status_text.text(f"Przetwarzanie dokumentu {idx + 1} z {total_files}: {file.name}...")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(file.getvalue())
                    tmp_pdf_path = tmp_file.name

                try:
                    report = orchestrator.process_invoice(pdf_path=tmp_pdf_path)
                    results.append({
                        "Nazwa Pliku": file.name,
                        "Nr Faktury": report.invoice_number,
                        "NIP": report.seller_nip,
                        "Kwota": report.total_gross,
                        "Kategoria": report.final_category,
                        "Pewność (%)": round(report.final_confidence * 100, 1),
                        "Status": report.decision_path,
                        "Uzasadnienie": report.reasoning,
                        "raw_text": report.raw_text 
                    })
                    if report.decision_path in stats:
                        stats[report.decision_path] += 1
                    else:
                        stats["PARSER_REJECTED"] += 1
                except Exception as e:
                    results.append({"Nazwa Pliku": file.name, "Status": "PARSER_REJECTED", "Uzasadnienie": str(e)})
                    stats["PARSER_REJECTED"] += 1
                finally:
                    if os.path.exists(tmp_pdf_path):
                        os.remove(tmp_pdf_path)

                progress_bar.progress((idx + 1) / total_files)

            status_text.success("✅ Zakończono analizę dokumentów.")
            st.session_state.batch_results = pd.DataFrame(results)
            st.session_state.batch_stats = stats

    # Prezentacja wyników i kolejka akceptacji
    if st.session_state.batch_results is not None:
        df = st.session_state.batch_results
        stats = st.session_state.batch_stats

        st.subheader("📊 Podsumowanie przetwarzania")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Zaksięgowano (ML)", stats.get("XGBOOST_FAST_TRACK", 0))
        col2.metric("Odzyskane (LLM)", stats.get("LLM_FALLBACK", 0))
        col3.metric("Odrzucone (Błąd)", stats.get("PARSER_REJECTED", 0))
        col4.metric("Do weryfikacji", stats.get("MANUAL_REVIEW", 0))
        col5.metric("Poprawione ręcznie", stats.get("RESOLVED_BY_HUMAN", 0))

        st.markdown("---")
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Pobierz plik integracyjny CSV dla ERP",
            data=csv_data,
            file_name="import_erp_faktury.csv",
            mime="text/csv",
        )

        # Kolejka weryfikacji z podglądem PDF
        manual_df = df[df['Status'] == 'MANUAL_REVIEW']
        if not manual_df.empty:
            st.markdown("---")
            st.subheader("🧑‍‍‍💻 Kolejka Akceptacji (Wymaga interwencji)")
            st.info("Poniższe pozycje wymagają weryfikacji. Sprawdź dokument w podglądzie i wybierz poprawną kategorię.")

            invoice_to_fix = st.selectbox(
                "Wybierz pozycję do skorygowania:", 
                manual_df['Nazwa Pliku'].tolist()
            )

            col_form, col_pdf = st.columns([1, 1])

            with col_form:
                selected_row = manual_df[manual_df['Nazwa Pliku'] == invoice_to_fix].iloc[0]
                st.write(f"**Nr faktury:** {selected_row['Nr Faktury']} | **NIP:** {selected_row['NIP']} | **Kwota:** {selected_row['Kwota']} PLN")
                st.caption(f"*Uzasadnienie kaskady: {selected_row['Uzasadnienie']}*")

                categories = ["OFFICE_SUPPLIES", "IT_HARDWARE", "IT_SERVICES", "TRAVEL_FLEET"]
                current_cat = str(selected_row['Kategoria'])
                default_idx = categories.index(current_cat) if current_cat in categories else 0

                with st.form(key=f"resolve_form_{invoice_to_fix}"):
                    new_category = st.selectbox("Właściwa kategoria:", categories, index=default_idx)
                    submit_override = st.form_submit_button("✅ Zatwierdź korektę", type="primary")

                    if submit_override:
                        idx = df.index[df['Nazwa Pliku'] == invoice_to_fix].tolist()[0]
                        st.session_state.batch_results.at[idx, 'Kategoria'] = new_category
                        st.session_state.batch_results.at[idx, 'Pewność (%)'] = 100.0
                        st.session_state.batch_results.at[idx, 'Status'] = 'RESOLVED_BY_HUMAN'

                        st.session_state.batch_stats['MANUAL_REVIEW'] -= 1
                        st.session_state.batch_stats['RESOLVED_BY_HUMAN'] += 1

                        save_feedback(
                            invoice_number=selected_row['Nr Faktury'], 
                            correct_category=new_category,
                            seller_nip = selected_row['NIP'],
                            raw_text = selected_row['raw_text']
                        )
                        st.rerun()

            with col_pdf:
                selected_file = next((f for f in uploaded_files if f.name == invoice_to_fix), None)
                if selected_file:
                    base64_pdf = base64.b64encode(selected_file.getvalue()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="450" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.warning("Podgląd dokumentu PDF jest niedostępny.")
        else:
            st.markdown("---")
            st.success("🎉 Wszystkie pozycje zostały zatwierdzone. Brak zadań w kolejce akceptacji.")

if __name__ == "__main__":
    main()