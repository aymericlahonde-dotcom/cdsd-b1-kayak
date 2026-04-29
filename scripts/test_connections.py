"""
Test des connexions API et AWS pour le projet Kayak
"""
import os
import requests
import boto3
from dotenv import load_dotenv

load_dotenv()

OWM_API_KEY = os.getenv("OWM_API_KEY")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")

print("=" * 50)
print("TEST 1 : Nominatim (GPS)")
print("=" * 50)
try:
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": "Paris, France", "format": "json", "limit": 1},
        headers={"User-Agent": "KayakProjectJedha/1.0"},
        timeout=10
    )
    data = r.json()
    if data:
        print(f"OK - Paris : lat={data[0]['lat']}, lon={data[0]['lon']}")
    else:
        print("ERREUR : Pas de résultat")
except Exception as e:
    print(f"ERREUR : {e}")

print()
print("=" * 50)
print("TEST 2 : OpenWeatherMap - One Call 3.0")
print("=" * 50)
# Test One Call 3.0 (nouvelle version)
try:
    r = requests.get(
        "https://api.openweathermap.org/data/3.0/onecall",
        params={"lat": 48.8566, "lon": 2.3522, "appid": OWM_API_KEY,
                "units": "metric", "exclude": "current,minutely,hourly,alerts"},
        timeout=10
    )
    print(f"Status 3.0: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"OK - {len(data.get('daily', []))} jours de prévisions")
    else:
        print(f"Réponse: {r.text[:200]}")
except Exception as e:
    print(f"Erreur 3.0: {e}")

print()
print("TEST 2b : OpenWeatherMap - Forecast 5 jours (gratuit)")
try:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={"lat": 48.8566, "lon": 2.3522, "appid": OWM_API_KEY,
                "units": "metric", "cnt": 5},
        timeout=10
    )
    print(f"Status forecast: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"OK - {len(data.get('list', []))} prévisions")
    else:
        print(f"Réponse: {r.text[:200]}")
except Exception as e:
    print(f"Erreur forecast: {e}")

print()
print("TEST 2c : OpenWeatherMap - Current weather (gratuit)")
try:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"lat": 48.8566, "lon": 2.3522, "appid": OWM_API_KEY, "units": "metric"},
        timeout=10
    )
    print(f"Status current: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"OK - Temp Paris: {data['main']['temp']}C")
    else:
        print(f"Réponse: {r.text[:200]}")
except Exception as e:
    print(f"Erreur current: {e}")

print()
print("=" * 50)
print("TEST 3 : AWS S3")
print("=" * 50)
try:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION
    )
    # Lister les buckets
    response = s3.list_buckets()
    buckets = [b["Name"] for b in response["Buckets"]]
    print(f"OK - Buckets disponibles : {buckets}")
    if S3_BUCKET in buckets:
        print(f"OK - Bucket '{S3_BUCKET}' trouvé")
    else:
        print(f"INFO - Bucket '{S3_BUCKET}' n'existe pas encore, il sera créé")
except Exception as e:
    print(f"ERREUR S3 : {e}")

print()
print("=" * 50)
print("TEST 4 : AWS RDS (check service)")
print("=" * 50)
try:
    rds = boto3.client(
        "rds",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION
    )
    response = rds.describe_db_instances()
    instances = response.get("DBInstances", [])
    if instances:
        for inst in instances:
            print(f"Instance existante : {inst['DBInstanceIdentifier']} - {inst['DBInstanceStatus']}")
    else:
        print("Aucune instance RDS existante - elle sera créée")
except Exception as e:
    print(f"ERREUR RDS : {e}")
