import os
import random
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# Katalog docelowy
OUTPUT_DIR = "data/edge_cases_pdfs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Słownik "trudnych" pozycji na fakturach
EDGE_CASES = [
    "Konsultacje technologiczno-organizacyjne za Q3",
    "Oplata manipulacyjna za przekroczenie limitu chmury",
    "Ekspres do kawy z wbudowanym modulem Wi-Fi i aplikacja",
    "Refaktura kosztow operacyjnych zgodnie z zal. 2",
    "Paliwo do agregatu pradotworczego w glownej serwerowni",
    "Szkolenie z MS Excel dla kierowcow floty regionalnej",
    "Materialy pomocnicze do wdrozenia infrastruktury AWS",
    "Abonament za system GPS do sledzenia przesylek IT",
    "Kable zasilajace do biurowych ekspresow cisnieniowych",
    "Zwrot kosztow dojazdu na targi technologiczne w Berlinie",
    "Licencja na oprogramowanie do zarzadzania flota pojazdow",
    "Wynajem przestrzeni na archiwum dokumentow papierowych",
    "Bilety lotnicze dla zespolu wdrozeniowego systemu ERP",
    "Zakup podkladek pod myszki oraz ziaren kawy Arabica",
    "Usluga doradcza - optymalizacja procesow logistycznych"
]

def generate_edge_cases(num_files=15):
    print(f"Rozpoczynam generowanie {num_files} trudnych faktur...")
    
    for i in range(num_files):
        random_nip = "".join([str(random.randint(0, 9)) for _ in range(10)])
        invoice_number = f"FV/EDGE/{datetime.now().year}/{1000 + i}"
        amount = round(random.uniform(500, 15000), 2)
        item_description = random.choice(EDGE_CASES)
        
        file_path = os.path.join(OUTPUT_DIR, f"trudna_faktura_{i+1:02d}.pdf")
        c = canvas.Canvas(file_path, pagesize=A4)
        
        # 1. Nagłówek faktury - wracamy do formatu bez "NR:"
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 800, f"FAKTURA VAT: {invoice_number}")
        
        c.setFont("Helvetica", 11)
        c.drawString(50, 780, f"Data wystawienia: {datetime.now().strftime('%Y-%m-%d')}")
        c.drawString(50, 765, f"Miejsce wystawienia: Warszawa")
        
        # 2. Sekcja Sprzedawcy i Nabywcy
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 720, "Sprzedawca:")
        c.setFont("Helvetica", 11)
        c.drawString(50, 700, "Firma Krzak sp. z o.o.")
        c.drawString(50, 685, f"NIP: {random_nip}")
        c.drawString(50, 670, "ul. Technologiczna 12/4")
        c.drawString(50, 655, "00-001 Warszawa")

        c.setFont("Helvetica-Bold", 12)
        c.drawString(300, 720, "Nabywca:")
        c.setFont("Helvetica", 11)
        c.drawString(300, 700, "Nasza Korporacja S.A.")
        c.drawString(300, 685, "NIP: 1112223344")
        c.drawString(300, 670, "ul. Biznesowa 1")
        c.drawString(300, 655, "00-999 Warszawa")
        
        # 3. Pozycje na fakturze
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 600, "Pozycje na fakturze:")
        c.setFont("Helvetica", 11)
        c.drawString(70, 580, f"1. {item_description}")
        
        # 4. Podsumowanie kwot - usunięto polskie znaki z etykiety
        c.line(50, 550, 550, 550) 
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 520, f"Kwota brutto do zaplaty: {amount:.2f} PLN")
        
        c.save()
        
    print(f"✅ Sukces! Wygenerowano {num_files} poprawnych faktur-pułapek w: {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_edge_cases(15)