"""
Setup Cloud : Upload S3 + Création RDS + ETL
"""
import os
import io
import time
import re
import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
S3_BUCKET             = os.getenv("S3_BUCKET")

RDS_IDENTIFIER = "kayak-jedha"
RDS_DB_NAME    = "kayak_db"
RDS_USER       = "kayak_admin"
RDS_PASSWORD   = "KayakJedha2026!"
RDS_PORT       = 5432

# ── Clients AWS ───────────────────────────────────────────────────────
s3  = boto3.client("s3",  aws_access_key_id=AWS_ACCESS_KEY_ID,
                   aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)
rds = boto3.client("rds", aws_access_key_id=AWS_ACCESS_KEY_ID,
                   aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)
ec2 = boto3.client("ec2", aws_access_key_id=AWS_ACCESS_KEY_ID,
                   aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 1 : Upload vers S3
# ══════════════════════════════════════════════════════════════════════
print("=" * 55)
print("ETAPE 1 : Upload vers S3")
print("=" * 55)

files = ["weather_cities.csv", "hotels_booking.csv", "weather_daily_detail.csv"]
for f in files:
    try:
        s3.upload_file(f, S3_BUCKET, f"raw/{f}")
        print(f"  OK  s3://{S3_BUCKET}/raw/{f}")
    except Exception as e:
        print(f"  ERREUR {f}: {e}")

# Vérification
resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="raw/")
print(f"\nContenu S3 bucket '{S3_BUCKET}':")
for obj in resp.get("Contents", []):
    kb = obj["Size"] / 1024
    print(f"  {obj['Key']} ({kb:.1f} KB)")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 2 : Créer ou réutiliser l'instance RDS
# ══════════════════════════════════════════════════════════════════════
print()
print("=" * 55)
print("ETAPE 2 : Instance RDS PostgreSQL")
print("=" * 55)

def get_my_public_ip():
    """Récupère l'IP publique pour le security group."""
    import urllib.request
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
    except Exception:
        return "0.0.0.0"

# Vérifier si l'instance existe déjà
existing = rds.describe_db_instances()["DBInstances"]
rds_endpoint = None

for inst in existing:
    if inst["DBInstanceIdentifier"] == RDS_IDENTIFIER:
        status = inst["DBInstanceStatus"]
        print(f"Instance existante: {RDS_IDENTIFIER} [{status}]")
        if status == "available":
            rds_endpoint = inst["Endpoint"]["Address"]
            print(f"Endpoint: {rds_endpoint}")
        break

if not rds_endpoint:
    print(f"Creation de l'instance RDS '{RDS_IDENTIFIER}'...")

    # Récupérer le VPC par défaut
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    vpc_id = vpcs["Vpcs"][0]["VpcId"]

    # Créer un security group dédié
    sg_name = "kayak-rds-sg"
    # Vérifier si le SG existe déjà
    sgs = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [sg_name]},
                 {"Name": "vpc-id", "Values": [vpc_id]}]
    )
    if sgs["SecurityGroups"]:
        sg_id = sgs["SecurityGroups"][0]["GroupId"]
        print(f"Security group existant: {sg_id}")
    else:
        sg = ec2.create_security_group(
            GroupName=sg_name,
            Description="Kayak Jedha RDS access",
            VpcId=vpc_id
        )
        sg_id = sg["GroupId"]
        print(f"Security group cree: {sg_id}")

    # Autoriser port 5432 depuis n'importe où (pour le projet scolaire)
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort":   RDS_PORT,
                "ToPort":     RDS_PORT,
                "IpRanges":   [{"CidrIp": "0.0.0.0/0", "Description": "Kayak project"}]
            }]
        )
        print(f"Regle ingress 5432 ajoutee")
    except Exception as e:
        if "already exists" in str(e).lower() or "Duplicate" in str(e):
            print("Regle 5432 deja existante")
        else:
            print(f"Avertissement regle SG: {e}")

    # Créer l'instance RDS
    try:
        rds.create_db_instance(
            DBInstanceIdentifier=RDS_IDENTIFIER,
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            EngineVersion="16.6",
            MasterUsername=RDS_USER,
            MasterUserPassword=RDS_PASSWORD,
            DBName=RDS_DB_NAME,
            AllocatedStorage=20,
            StorageType="gp2",
            PubliclyAccessible=True,
            VpcSecurityGroupIds=[sg_id],
            BackupRetentionPeriod=0,  # Pas de backup pour économiser
            MultiAZ=False,
            Tags=[{"Key": "Project", "Value": "KayakJedha"}]
        )
        print("Instance RDS en cours de creation...")
    except rds.exceptions.DBInstanceAlreadyExistsFault:
        print("Instance deja en creation/existante")

    # Attendre que l'instance soit disponible (~5-10 min)
    print("Attente disponibilite RDS (peut prendre 5-10 min)...")
    waiter = rds.get_waiter("db_instance_available")
    waiter.wait(
        DBInstanceIdentifier=RDS_IDENTIFIER,
        WaiterConfig={"Delay": 30, "MaxAttempts": 40}
    )

    # Récupérer l'endpoint
    resp = rds.describe_db_instances(DBInstanceIdentifier=RDS_IDENTIFIER)
    inst = resp["DBInstances"][0]
    rds_endpoint = inst["Endpoint"]["Address"]
    print(f"RDS disponible ! Endpoint: {rds_endpoint}")

# Mettre à jour le .env
rds_uri = f"postgresql+psycopg2://{RDS_USER}:{RDS_PASSWORD}@{rds_endpoint}:{RDS_PORT}/{RDS_DB_NAME}"
env_path = ".env"
with open(env_path, "r") as f:
    content = f.read()
content = re.sub(r"RDS_URI=.*", f"RDS_URI={rds_uri}", content)
with open(env_path, "w") as f:
    f.write(content)
print(f"Fichier .env mis a jour avec l'endpoint RDS")
print(f"RDS_URI={rds_uri}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 3 : ETL S3 → RDS
# ══════════════════════════════════════════════════════════════════════
print()
print("=" * 55)
print("ETAPE 3 : ETL S3 -> RDS PostgreSQL")
print("=" * 55)

# Installer psycopg2 si nécessaire
try:
    import psycopg2
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2

from sqlalchemy import create_engine, text

engine = create_engine(rds_uri)

# EXTRACT depuis S3
def read_s3_csv(key):
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()))

print("Extract depuis S3...")
df_weather = read_s3_csv("raw/weather_cities.csv")
df_hotels  = read_s3_csv("raw/hotels_booking.csv")
print(f"  Meteo: {df_weather.shape}")
print(f"  Hotels: {df_hotels.shape}")

# TRANSFORM
print("Transform...")
df_weather_clean = df_weather[[
    "city_id", "city", "lat", "lon",
    "temp_max_mean", "pop_mean", "rain_total",
    "humidity_mean", "weather_score", "rank"
]].copy()
df_weather_clean["temp_max_mean"] = df_weather_clean["temp_max_mean"].round(1)
df_weather_clean["weather_score"] = df_weather_clean["weather_score"].round(2)

df_hotels_clean = df_hotels[[
    "city_id", "city", "hotel_name", "url",
    "lat", "lon", "score", "reviews", "description"
]].copy()
df_hotels_clean = df_hotels_clean.dropna(subset=["hotel_name"])
df_hotels_clean["score"] = pd.to_numeric(df_hotels_clean["score"], errors="coerce")
df_hotels_clean["hotel_id"] = range(1, len(df_hotels_clean) + 1)

# LOAD
print("Load vers RDS...")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS hotels"))
    conn.execute(text("DROP TABLE IF EXISTS cities_weather"))
    conn.commit()

df_weather_clean.to_sql("cities_weather", engine, if_exists="replace", index=False)
print(f"  Table 'cities_weather': {len(df_weather_clean)} lignes")

df_hotels_clean.to_sql("hotels", engine, if_exists="replace", index=False)
print(f"  Table 'hotels': {len(df_hotels_clean)} lignes")

# Vérification
print()
print("Verification depuis RDS:")
with engine.connect() as conn:
    top5 = pd.read_sql(
        text("SELECT city, weather_score, rank FROM cities_weather ORDER BY rank LIMIT 5"),
        conn
    )
    print("Top 5 destinations:")
    print(top5.to_string(index=False))

    top_hotels = pd.read_sql(
        text("SELECT hotel_name, city, score FROM hotels WHERE score IS NOT NULL ORDER BY score DESC LIMIT 5"),
        conn
    )
    print("\nTop 5 hotels:")
    print(top_hotels.to_string(index=False))

print()
print("=== CLOUD SETUP TERMINE ===")
print(f"S3  : s3://{S3_BUCKET}/raw/")
print(f"RDS : {rds_endpoint}")
print(f"URI : {rds_uri}")
