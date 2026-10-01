import glob
import os
import re
import pdfplumber
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from typing import Optional

#pydantic rozwiazuje problem tj. gdy w  __init__(self, kwota: float) mamy kwote jako int, to jak ktos przekaze argument kwota = "za darmo", to program przyjmie
#tą wartość i wywali się gdzieś później. Pydantic od razu rzuca Valueerror, i dodatkowo konwertuje na dobre typy np tutaj: "150.00" -> 150.00

# ==========================================
# 1. KONTRAKT DANYCH (SCHEMA PYDANTIC)
# ==========================================
class ParsedInvoice(BaseModel):
    """Schemat wyekstrahowanych danych z faktury."""
    
    invoice_number: str
    issue_date: str
    seller_name: str
    seller_nip: str
    total_net: Optional[float] = 0.0
    total_vat: Optional[float] = 0.0
    total_gross: float
    raw_text: str  # Przechowujemy cały tekst z PDF - posłuży do TF-IDF w XGBoost!

    # Pydantic pozwala na definiowanie własnych reguł sprawdzających:
    @field_validator("seller_nip")
    @classmethod
    def validate_nip_format(cls, value: str) -> str: #dodaje cls, bo musze przekazac to jesli robie classmethod
        # Usuwamy ewentualne spacje i myślniki z parsera
        clean_nip = value.replace("-", "").replace(" ", "").strip()
        if len(clean_nip) != 10 or not clean_nip.isdigit():
            raise ValueError(f"NIP musi składać się z dokładnie 10 cyfr, otrzymano: '{value}'")
        return clean_nip

    @model_validator(mode="after")
    def validate_totals_math(self):
        # Pomijamy walidację matematyczną dla edge caseow, które nie mają rozbicia na Netto/VAT
        if self.total_net == 0.0 and self.total_vat == 0.0:
            return self
        
        # Sprawdzamy, czy różnica nie przekracza 2 groszy
        difference = abs(self.total_net + self.total_vat - self.total_gross)
        if difference > 0.02:
            raise ValueError(
                f"Błąd sumowania: Netto ({self.total_net}) + VAT ({self.total_vat}) != Brutto ({self.total_gross})"
            )
        return self #zawsze trzeba zwrocic cos w Pydantic v2
    
# ==========================================
# 2. SILNIK PARSUJĄCY (INVOICE PARSER)
# ==========================================
class InvoiceParser:
    """Odpowiada za ekstrakcję tekstu i mapowanie dokumentu PDF na model ParsedInvoice."""

    def __init__(self):
        # Kompilacja wzorców Regex przy starcie klasy (optymalizacja wydajnościowa)
        self._patterns = {
            "invoice_number": re.compile(r"FAKTURA VAT(?: NR)?:\s*(\S+)"),
            "issue_date": re.compile(r"Data wystawienia:\s*(\d{4}-\d{2}-\d{2})"),
            "seller_name": re.compile(r"(?:Nazwa|Sprzedawca):\s*([^\n]+)"),
            "seller_nip": re.compile(r"NIP:\s*(\d{10})"),
            "total_net": re.compile(r"Razem Netto:\s*([\d\.]+)\s*PLN"),
            "total_vat": re.compile(r"Razem VAT:\s*([\d\.]+)\s*PLN"),
            "total_gross": re.compile(r"(?:DO ZAP[ŁL]ATY|Kwota brutto(?: do zap[lł]aty)?):\s*([\d\.\,]+)\s*PLN", re.IGNORECASE),
        }
        
    def extract_raw_text(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Nie odnaleziono pliku: {pdf_path}")

        extracted_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)

        return "\n".join(extracted_text)

    def _extract_by_pattern(self, pattern: re.Pattern, text: str, field_name: str) -> str:
        match = pattern.search(text)
        if not match:
            raise ValueError(f"Nie udało się odnaleźć pola '{field_name}' w dokumencie.")
        return match.group(1).strip()

    def parse(self, pdf_path: str) -> ParsedInvoice:
        raw_text = self.extract_raw_text(pdf_path)

        # Pola wymagane (rzuci błędem, jeśli ich nie ma)
        invoice_number = self._extract_by_pattern(self._patterns["invoice_number"], raw_text, "invoice_number")
        issue_date = self._extract_by_pattern(self._patterns["issue_date"], raw_text, "issue_date")
        seller_name = self._extract_by_pattern(self._patterns["seller_name"], raw_text, "seller_name")
        seller_nip = self._extract_by_pattern(self._patterns["seller_nip"], raw_text, "seller_nip")
        total_gross_str = self._extract_by_pattern(self._patterns["total_gross"], raw_text, "total_gross")

        # Pola opcjonalne (miękkie sprawdzenie bez rzucania ValueError)
        match_net = self._patterns["total_net"].search(raw_text)
        total_net_val = float(match_net.group(1).strip()) if match_net else 0.0

        match_vat = self._patterns["total_vat"].search(raw_text)
        total_vat_val = float(match_vat.group(1).strip()) if match_vat else 0.0

        # Pydantic sam skonwertuje stringi liczbowe na float i uruchomi walidację
        return ParsedInvoice(
            invoice_number=invoice_number,
            issue_date=issue_date,
            seller_name=seller_name,
            seller_nip=seller_nip,
            total_net=total_net_val,
            total_vat=total_vat_val,
            total_gross=float(total_gross_str.replace(",", ".")), # Zamiana ewentualnego przecinka na kropkę dla float
            raw_text=raw_text,
        )