class InvoiceItem:
    """Reprezentuje pojedynczą pozycję na fakturze (np. 'Laptop Dell', 'Konsultacje IT')."""
    
    def __init__(self, description: str, net_amount: float, vat_rate: float):
        # Twoim zadaniem będzie przypisanie zmiennych i dodanie logiki liczącej
        # kwotę VAT oraz kwotę brutto dla tej jednej pozycji.
        if net_amount < 0:
            raise ValueError(f"Kwota netto nie może być ujemna: {net_amount}")
        
        # Zabezpieczenie: jeśli ktoś poda 23 zamiast 0.23
        if vat_rate > 1.0:
            raise ValueError(f"Stawka VAT powinna być ułamkiem (np. 0.23 dla 23%), otrzymano: {vat_rate}")
        self.description = description
        self.net_amount = round(net_amount, 2)
        self.vat_rate = vat_rate

    @property #dekorator tak zeby w razie czego mozna bylo pisac item.vat_amount, bo bez tego by bylo item.vat_amount()
    def vat_amount(self) -> float:
        """Zwraca wyliczoną kwotę VAT, zaokrągloną do 2 miejsc po przecinku."""
        return round(self.net_amount * self.vat_rate, 2)
        
    @property
    def gross_amount(self) -> float:
        """Zwraca wyliczoną kwotę brutto."""
        return round(self.net_amount + self.vat_amount, 2)


class Invoice:
    """Reprezentuje cały dokument faktury składający się z wielu pozycji."""
    
    def __init__(self, invoice_number: str, issue_date: str,seller_name: str, seller_nip: str, items: list[InvoiceItem]):
        # Przypisanie atrybutów.
        self.invoice_number = invoice_number
        self.issue_date = issue_date
        self.seller_name = seller_name
        self.seller_nip = seller_nip
        self.items = items
    
    @property  
    def total_net(self) -> float:
        """Suma kwot netto ze wszystkich pozycji."""
        return round( sum(item.net_amount for item in self.items), 2)    
        
    @property
    def total_vat(self) -> float:
        """Suma kwot VAT ze wszystkich pozycji."""
        return round( sum(item.vat_amount for item in self.items), 2)
    @property
    def total_gross(self) -> float:
        """Suma kwot brutto ze wszystkich pozycji."""
        return round( sum(item.gross_amount for item in self.items), 2)
    
#=============================================================================================================#

from faker import Faker
import random

# Zaprojektujmy 4 główne kategorie kosztów firmowych:

# IT_HARDWARE (np. Laptopy, monitory, kable)

# IT_SERVICES (np. Subskrypcje chmurowe AWS/Azure, licencje GitHub, hosting)

# OFFICE_SUPPLIES (np. Papier ksero, tonery, kawa, środki czystości)

# TRAVEL_FLEET (np. Paliwo PB95, bilet PKP, hotel, parking)

class InvoiceFactory:
    """Fabryka odpowiedzialna za produkcję syntetycznych danych faktur."""

    def __init__(self, seed: int = 42):
        self.fake = Faker("pl_PL")  # Polska wersja generatora (tworzy polskie nazwy firm, adresy)
        Faker.seed(seed)
        random.seed(seed)

        # Nasza baza 'stałych dostawców' - to na nich XGBoost nauczy się wzorców!
        # Klucz to NIP, a wartość to krotka: (Nazwa firmy, Typowa kategoria)
        self.known_vendors = {
            "5261040828": ("Orlen Paliwa Sp. z o.o.", "TRAVEL_FLEET"),
            "5213456789": ("Dell Polska Sp. z o.o.", "IT_HARDWARE"),
            "1234567890": ("Amazon Web Services EMEA", "IT_SERVICES"),
            "9876543210": ("Biuromax Artykuły Biurowe", "OFFICE_SUPPLIES"),
        }

        # Przykładowe pozycje przypisane do kategorii
        self.sample_catalog = {
            "TRAVEL_FLEET": [
                "Olej napędowy Verva", "Benzyna Pb95", "Opłata autostradowa A2", "Hotel Warszawa doba"
            ],
            "IT_HARDWARE": [
                "Monitor Dell 27 cali", "Klawiatura mechaniczna", "Laptop Lenovo ThinkPad", "Kabel USB-C"
            ],
            "IT_SERVICES": [
                "Hosting serwera VPS", "Subskrypcja Azure Cloud", "Licencja JetBrains", "Domena internetowa"
            ],
            "OFFICE_SUPPLIES": [
                "Papier ksero A4 5 ryz", "Toner do drukarki HP", "Kawa ziarnista Arabica 1kg", "Segregator biurowy"
            ]
        }

        # Pozycje niejednoznaczne, które celowo mają zmylić prosty model:
        self.ambiguous_items = [
            "Usługa doradcza i wsparcie",
            "Materiały eksploatacyjne różne",
            "Refaktura kosztów projektu",
            "Opłata manipulacyjna",
            "Rozliczenie okresowe"
        ]
    def _generate_items_for_category(self, category: str) -> list[InvoiceItem]: # _ oznaczamy metode prywatną, którą wykorzystujemy tylko w obrebie klasy, tak dla czytelnosci jest konwencja zeby ktos sie nie musial zastanawiac po co jest ta metoda
        """
        ZADANIE 1:
        Losuje od 1 do 3 pozycji z katalogu odpowiadającego danej kategorii.
        Dla każdej pozycji losuje cenę netto (np. od 20 zł do 3000 zł) oraz stawkę VAT (np. 0.23).
        Tworzy obiekty InvoiceItem i zwraca je jako listę.
        """
        # Bezpiecznik: jeśli nie ma kategorii w katalogu, weź pozycje trudne/niejednoznaczne
        category_items = self.sample_catalog.get(category, self.ambiguous_items)
        
        # Losujemy ile pozycji ma mieć faktura (od 1 do 3)
        num_items = random.randint(1, min(3, len(category_items)))
        
        # Losujemy pozycje bez powtórzeń
        selected_descriptions = random.sample(category_items, k=num_items)
        
        items = []
        for desc in selected_descriptions:
            # Realistyczna kwota netto z groszami (np. 149.99 zł)
            net_amount = round(random.uniform(50.0, 2500.0), 2)
            
            # W B2B dominującą stawką jest 23% (0.23)
            vat_rate = 0.23
            
            items.append(InvoiceItem(description=desc, net_amount=net_amount, vat_rate=vat_rate))
        
        return items    
        

    def create_random_invoice(self, threshold: float = 0.85) -> tuple[Invoice, str]:
        """
        ZADANIE 2:
        Główna metoda tworząca fakturę:
        1. Losuje jednego ze sprzedawców z self.known_vendors (lub w np. 15% (tutaj parametr threshold mowi ile ma byc % ZNANYCH sprzedawcow)przypadków tworzy nowego, nieznanego sprzedawcę - cold start!).
        2. Pobiera kategorię tego sprzedawcy.
        3. Generuje pozycje za pomocą _generate_items_for_category.
        4. Generuje numer faktury (np. 'FV/2024/09/' + losowe cyfry) oraz datę.
        5. Zwraca krotkę: (obiekt Invoice, etykieta_kategorii) -> etykieta przyda się nam potem do uczenia ML!
        """
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("Threshold musi być pomiędzy 0 a 1")
        
        #Tworzymy fakeowy numer faktury i date wystawienia
        invoice_number = f"FV/{self.fake.year()}/{random.randint(1000, 9999)}"
        issue_date = self.fake.date_this_year().strftime("%Y-%m-%d")            
        
        if random.random() < threshold:
            seller_nip = random.choice( list(self.known_vendors.keys()) )
            seller_name, category = self.known_vendors[seller_nip]
        
        else:
            seller_nip = self.fake.nip()
            seller_name = self.fake.company()
            category = random.choice(list(self.sample_catalog.keys()))
        
        
        items = self._generate_items_for_category(category=category)
                    
        invoice = Invoice(
                        invoice_number=invoice_number,
                        issue_date=issue_date,
                        seller_name=seller_name,
                        seller_nip=seller_nip,
                        items=items
                    )
        return invoice, category
        
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

class PDFRenderer:
    """Odpowiada wyłącznie za wyrenderowanie obiektu Invoice do pliku PDF."""

    def __init__(self, output_dir: str = "data/raw_pdfs"):
        self.output_dir = output_dir
        # Upewniamy się, że folder docelowy istnieje na dysku
        os.makedirs(self.output_dir, exist_ok=True)

    # PDFrender traktuje kartke jako uklad wspolrzednych - lewy dolny rog jest (0,0), a kartka A4 ma wysokosc jakos ok 870 px
    def render(self, invoice: Invoice, filename: str) -> str:
        """
        Rysuje fakturę na formacie A4 i zapisuje na dysku.
        Zwraca pełną ścieżkę do zapisanego pliku.
        """
        file_path = os.path.join(self.output_dir, filename)
        
        # 1. Tworzymy obiekt płótna (canvas) o wymiarach A4
        c = canvas.Canvas(file_path, pagesize=A4)
        
        # y_cursor to nasza pozycja pionowa na kartce - startujemy blisko góry
        y = 800 

        # 2. Rysujemy nagłówek dokumentu
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, f"FAKTURA VAT: {invoice.invoice_number}")
        y -= 25

        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Data wystawienia: {invoice.issue_date}")
        y -= 30

        # 3. Rysujemy dane Sprzedawcy
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "SPRZEDAWCA:")
        y -= 15
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Nazwa: {invoice.seller_name}")
        y -= 15
        c.drawString(50, y, f"NIP: {invoice.seller_nip}")
        y -= 40

        # 4. Rysujemy tabelę z pozycjami
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Pozycja")
        c.drawString(300, y, "Netto [PLN]")
        c.drawString(400, y, "VAT")
        c.drawString(480, y, "Brutto [PLN]")
        y -= 15
        
        # Linia oddzielająca nagłówek tabeli
        c.line(50, y, 550, y)
        y -= 15

        # Pętla po pozycjach faktury
        c.setFont("Helvetica", 9)
        for item in invoice.items:
            c.drawString(50, y, item.description)
            c.drawString(300, y, f"{item.net_amount:.2f}")
            c.drawString(400, y, f"{int(item.vat_rate * 100)}%")
            c.drawString(480, y, f"{item.gross_amount:.2f}")
            y -= 18

        y -= 15
        c.line(50, y, 550, y)
        y -= 25

        # 5. Podsumowanie finansowe
        c.setFont("Helvetica-Bold", 11)
        c.drawString(350, y, f"Razem Netto: {invoice.total_net:.2f} PLN")
        y -= 18
        c.drawString(350, y, f"Razem VAT: {invoice.total_vat:.2f} PLN")
        y -= 18
        c.drawString(350, y, f"DO ZAPLATY: {invoice.total_gross:.2f} PLN")

        # 6. Zapisanie pliku
        c.save()
        return file_path
    
    
import csv

def generate_dataset(num_invoices: int = 50):
    factory = InvoiceFactory(seed=42)
    renderer = PDFRenderer(output_dir="data/raw_pdfs")
    
    metadata_records = []
    
    print(f"Generowanie {num_invoices} faktur...")
    for i in range(1, num_invoices + 1):
        filename = f"faktura_{i:03d}.pdf"
        invoice, category = factory.create_random_invoice()
        
        renderer.render(invoice, filename)
        
        metadata_records.append({
            "filename": filename,
            "category": category,
            "seller_nip": invoice.seller_nip,
            "total_gross": invoice.total_gross
        })

    # Zapisujemy etykiety do pliku CSV (nasz zbiór treningowo-testowy)
    with open("data/dataset_labels.csv", mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "category", "seller_nip", "total_gross"])
        writer.writeheader()
        writer.writerows(metadata_records)

    print("Gotowe! Wygenerowano pliki PDF oraz data/dataset_labels.csv.")


def main():
    """Główna pętla sterująca."""
    generate_dataset(num_invoices=1000)    
    print("Gotowe! Wygenerowano pliki PDF oraz data/dataset_labels.csv.")

if __name__ == "__main__":
    main()