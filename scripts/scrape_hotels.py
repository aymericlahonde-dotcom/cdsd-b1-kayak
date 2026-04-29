"""
Scraping des hôtels sur Booking.com via Selenium + BeautifulSoup
Collecte pour les 35 villes françaises (20 hôtels par ville)
"""
import os
import time
import json
import re
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def create_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    return driver

def scrape_city_hotels(driver, city_name, city_id, n_hotels=20):
    """Scrape les hôtels d'une ville sur Booking.com."""
    hotels = []
    city_encoded = city_name.replace(" ", "+")
    url = (
        f"https://www.booking.com/searchresults.html"
        f"?ss={city_encoded}&lang=fr&sb=1&src=searchresults"
        f"&ac_langcode=fr&dest_type=city"
    )

    try:
        driver.get(url)
        time.sleep(4)

        # Fermer le popup cookies
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            btn.click()
            time.sleep(1)
        except Exception:
            pass

        # Attendre les résultats
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="property-card"]')
                )
            )
        except Exception:
            pass

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.find_all("div", {"data-testid": "property-card"})

        if not cards:
            # Essayer sélecteurs alternatifs
            cards = soup.find_all("div", class_=re.compile(r"sr_item|property_card"))

        for card in cards[:n_hotels]:
            try:
                # Nom
                name = None
                for sel in [
                    {"data-testid": "title"},
                    {"class": re.compile(r"fcab3ed991|e13098a59f")},
                ]:
                    tag = card.find(["div", "span", "h3"], sel)
                    if tag:
                        name = tag.get_text(strip=True)
                        break
                if not name:
                    name = "Hotel inconnu"

                # URL
                link = card.find("a", {"data-testid": "title-link"})
                if not link:
                    link = card.find("a", href=re.compile(r"/hotel/"))
                hotel_url = link["href"] if link else ""
                if hotel_url and not hotel_url.startswith("http"):
                    hotel_url = "https://www.booking.com" + hotel_url

                # Score
                score = None
                score_tag = card.find(
                    "div",
                    class_=re.compile(r"ac4a7896c7|b5cd09854e|d10a6220b4")
                )
                if score_tag:
                    txt = score_tag.get_text(strip=True).replace(",", ".")
                    m = re.search(r"(\d+\.?\d*)", txt)
                    if m:
                        score = float(m.group(1))
                        if score > 10:
                            score = score / 10

                # Nombre d'avis
                reviews = None
                for r_sel in [
                    {"data-testid": "review-score"},
                    {"class": re.compile(r"abf093bdfe|b5cd09854e")},
                ]:
                    rev_tag = card.find(["div", "span"], r_sel)
                    if rev_tag:
                        all_text = rev_tag.get_text(" ", strip=True)
                        m = re.search(r"(\d[\d\s]*)\s*(?:avis|commentaire|évaluation)", all_text, re.I)
                        if m:
                            reviews = m.group(1).replace(" ", "")
                        break

                # Coordonnées GPS
                lat = card.get("data-lat") or card.get("data-coordinate-lat")
                lon = card.get("data-lon") or card.get("data-coordinate-lon")

                # Description / adresse
                addr_tag = card.find(["span", "div"], {"data-testid": "address"})
                if not addr_tag:
                    addr_tag = card.find(
                        ["span", "div"],
                        class_=re.compile(r"f4bd0794db|aee5343fdb")
                    )
                description = addr_tag.get_text(strip=True) if addr_tag else ""

                hotels.append({
                    "city_id":     city_id,
                    "city":        city_name,
                    "hotel_name":  name,
                    "url":         hotel_url,
                    "lat":         float(lat) if lat else None,
                    "lon":         float(lon) if lon else None,
                    "score":       score,
                    "reviews":     reviews,
                    "description": description,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"\nErreur scraping {city_name}: {e}")

    return hotels


# ── Main ──────────────────────────────────────────────────────────────

df_coords = pd.read_csv("cities_coords.csv")

print("=== SCRAPING BOOKING.COM ===")
print(f"Villes: {len(df_coords)} | Hotels cibles: 20/ville\n")

driver = create_driver()
all_hotels = []

for _, row in tqdm(df_coords.iterrows(), total=len(df_coords), desc="Hotels"):
    hotels = scrape_city_hotels(driver, row["city"], row["city_id"], n_hotels=20)
    all_hotels.extend(hotels)
    # Pause pour ne pas être bloqué
    time.sleep(3)

driver.quit()

df_hotels = pd.DataFrame(all_hotels)

# Nettoyage
df_hotels["score"] = pd.to_numeric(df_hotels["score"], errors="coerce")
df_hotels = df_hotels[df_hotels["hotel_name"] != "Hotel inconnu"].copy()
df_hotels["hotel_id"] = range(1, len(df_hotels) + 1)

# Stats
print(f"\n=== RÉSULTATS ===")
print(f"Hotels collectes: {len(df_hotels)}")
print(f"Villes couvertes: {df_hotels['city'].nunique()}")
print(f"Hotels avec score: {df_hotels['score'].notna().sum()}")
print(f"Hotels avec GPS: {df_hotels['lat'].notna().sum()}")
print(f"\nTop 10 hotels (score):")
top = (
    df_hotels.dropna(subset=["score"])
    .sort_values("score", ascending=False)
    [["hotel_name", "city", "score"]]
    .head(10)
)
print(top.to_string(index=False))

# Sauvegarde
df_hotels.to_csv("hotels_booking.csv", index=False)
print(f"\nFichier sauvegarde: hotels_booking.csv")
