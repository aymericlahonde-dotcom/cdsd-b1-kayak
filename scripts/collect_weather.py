"""
Collecte GPS (Nominatim) + Meteo (OWM Forecast) pour les 35 villes françaises
"""
import os
import time
import requests
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

OWM_API_KEY = os.getenv("OWM_API_KEY")

CITIES = [
    "Mont Saint Michel", "St Malo", "Bayeux", "Le Havre", "Rouen",
    "Paris", "Amiens", "Lille", "Strasbourg", "Chateau du Haut Koenigsbourg",
    "Colmar", "Eguisheim", "Besancon", "Dijon", "Annecy",
    "Grenoble", "Lyon", "Gorges du Verdon", "Bormes les Mimosas", "Cassis",
    "Marseille", "Aix en Provence", "Avignon", "Uzes", "Nimes",
    "Aigues Mortes", "Saintes Maries de la mer", "Collioure", "Carcassonne", "Ariege",
    "Toulouse", "Montauban", "Biarritz", "Bayonne", "La Rochelle"
]

# ── Étape 1 : Coordonnées GPS via Nominatim ───────────────────────────

def get_coordinates(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{city_name}, France", "format": "json", "limit": 1}
    headers = {"User-Agent": "KayakProjectJedha/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if data:
            return {"city": city_name, "lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
        return None
    except Exception as e:
        print(f"Erreur GPS {city_name}: {e}")
        return None

print("=== ÉTAPE 1 : Coordonnées GPS ===")
coords_list = []
for city in tqdm(CITIES, desc="GPS"):
    result = get_coordinates(city)
    if result:
        coords_list.append(result)
    time.sleep(1)  # Respecter la limite Nominatim

df_coords = pd.DataFrame(coords_list)
df_coords["city_id"] = range(1, len(df_coords) + 1)
print(f"OK - {len(df_coords)} villes geolocalises")
print(df_coords.head())

# ── Étape 2 : Météo via OWM Forecast (5 jours, gratuit) ──────────────

def get_weather_forecast(lat, lon, city_id, city_name):
    """
    Utilise l'API Forecast OWM (gratuite) : 5 jours, intervalles 3h.
    On agrège par jour pour obtenir les stats journalières.
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat, "lon": lon,
        "appid": OWM_API_KEY,
        "units": "metric",
        "lang": "fr",
        "cnt": 40  # 5 jours × 8 créneaux/jour
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if r.status_code != 200:
            print(f"Erreur OWM {city_name}: {data.get('message', r.status_code)}")
            return []

        # Agréger par date
        daily = {}
        for item in data.get("list", []):
            date = pd.to_datetime(item["dt"], unit="s").strftime("%Y-%m-%d")
            if date not in daily:
                daily[date] = {
                    "temps": [], "humidity": [], "pop": [],
                    "rain_mm": 0, "wind_speeds": [], "descriptions": []
                }
            daily[date]["temps"].append(item["main"]["temp"])
            daily[date]["humidity"].append(item["main"]["humidity"])
            daily[date]["pop"].append(item.get("pop", 0))
            daily[date]["rain_mm"] += item.get("rain", {}).get("3h", 0)
            daily[date]["wind_speeds"].append(item["wind"]["speed"])
            daily[date]["descriptions"].append(item["weather"][0]["description"])

        records = []
        for date, vals in daily.items():
            records.append({
                "city_id":      city_id,
                "city":         city_name,
                "date":         date,
                "temp_min":     round(min(vals["temps"]), 1),
                "temp_max":     round(max(vals["temps"]), 1),
                "temp_mean":    round(sum(vals["temps"]) / len(vals["temps"]), 1),
                "humidity":     round(sum(vals["humidity"]) / len(vals["humidity"]), 1),
                "pop":          round(sum(vals["pop"]) / len(vals["pop"]), 2),
                "rain_mm":      round(vals["rain_mm"], 1),
                "wind_speed":   round(sum(vals["wind_speeds"]) / len(vals["wind_speeds"]), 1),
                "description":  vals["descriptions"][len(vals["descriptions"]) // 2]  # Description de mi-journée
            })
        return records
    except Exception as e:
        print(f"Erreur meteo {city_name}: {e}")
        return []

print("\n=== ÉTAPE 2 : Données météo ===")
all_weather = []
for _, row in tqdm(df_coords.iterrows(), total=len(df_coords), desc="Meteo"):
    records = get_weather_forecast(row["lat"], row["lon"], row["city_id"], row["city"])
    all_weather.extend(records)
    time.sleep(0.3)

df_weather = pd.DataFrame(all_weather)
print(f"OK - {len(df_weather)} enregistrements meteo")
print(f"   Periode: {df_weather['date'].min()} -> {df_weather['date'].max()}")

# ── Étape 3 : Score météo & classement ───────────────────────────────

def normalize(series, reverse=False):
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    normalized = (series - mn) / (mx - mn) * 100
    return (100 - normalized) if reverse else normalized

df_agg = df_weather.groupby(["city_id", "city"]).agg(
    temp_max_mean=("temp_max",  "mean"),
    pop_mean=     ("pop",       "mean"),
    rain_total=   ("rain_mm",   "sum"),
    humidity_mean=("humidity",  "mean"),
    wind_mean=    ("wind_speed","mean")
).reset_index()

df_agg["score_temp"] = normalize(df_agg["temp_max_mean"])
df_agg["score_rain"] = normalize(df_agg["pop_mean"],    reverse=True)
df_agg["score_vol"]  = normalize(df_agg["rain_total"],  reverse=True)
df_agg["score_hum"]  = normalize(df_agg["humidity_mean"], reverse=True)

df_agg["weather_score"] = (
    df_agg["score_temp"] * 0.40 +
    df_agg["score_rain"] * 0.30 +
    df_agg["score_vol"]  * 0.20 +
    df_agg["score_hum"]  * 0.10
).round(2)

df_ranking = df_agg.sort_values("weather_score", ascending=False).reset_index(drop=True)
df_ranking["rank"] = df_ranking.index + 1

df_weather_final = df_ranking.merge(df_coords[["city_id", "lat", "lon"]], on="city_id")

print("\n=== TOP 10 DESTINATIONS (meteo) ===")
print(df_weather_final[["rank", "city", "temp_max_mean", "pop_mean", "rain_total", "weather_score"]].head(10).to_string(index=False))

# Sauvegarde
df_weather_final.to_csv("weather_cities.csv", index=False)
df_weather.to_csv("weather_daily_detail.csv", index=False)
df_coords.to_csv("cities_coords.csv", index=False)
print("\nFichiers sauvegardes: weather_cities.csv, weather_daily_detail.csv, cities_coords.csv")
