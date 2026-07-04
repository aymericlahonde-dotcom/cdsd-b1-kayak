# Dossier projet — Plan your trip with Kayak

**Certification Jedha CDSD (RNCP35288) — Bloc 1 : Construction et alimentation d'une infrastructure de gestion de données**
**Auteur :** Aymeric Lahonde — promotion Jedha CDSD 2026

---

## 1. Contexte et objectifs

Kayak, moteur de recherche de voyages du groupe Booking Holdings, constate qu'environ 70 %
des utilisateurs souhaitent davantage d'informations sur leur destination avant de réserver.
L'entreprise veut donc recommander les meilleures villes françaises selon deux axes : la
**météo** (confort du séjour) et les **hôtels** disponibles (qualité, notes).

Aucune donnée n'est fournie au départ. Le travail attendu relève du **Data Engineering** :
collecter la donnée depuis des sources externes, la stocker dans une architecture cloud
(Data Lake + Data Warehouse) et la restituer sous forme exploitable.

**Périmètre :** 35 villes françaises listées par Kayak.

**Livrables attendus :**
1. Un pipeline ETL complet et reproductible.
2. Un Data Lake S3 contenant les données brutes.
3. Une base SQL (RDS PostgreSQL) contenant les données nettoyées.
4. Deux cartes interactives : Top 5 destinations (météo) et Top 20 hôtels.

---

## 2. Architecture

```
Nominatim ──► OpenWeather ──► Booking.com (Selenium)
   (GPS)        (météo 5j)       (hôtels)
     │              │                │
     └──────────────┴────────────────┘
                    ▼
            CSV locaux (data/)
                    ▼
        AWS S3 — Data Lake (raw/)
                    ▼
   AWS RDS PostgreSQL — Data Warehouse
                    ▼
      Plotly Express — 2 cartes HTML
```

**Pourquoi deux niveaux de stockage ?**
- **S3 (Data Lake)** : stockage brut, peu coûteux, schéma libre. C'est la source de vérité :
  si l'ETL casse, on peut rejouer depuis les données brutes.
- **RDS PostgreSQL (Data Warehouse)** : données nettoyées et structurées, requêtables en SQL
  par les analystes / dashboards.

**Stack technique :** Python 3.11 · pandas / numpy · requests · BeautifulSoup4 · Selenium
(Chrome headless) · boto3 (S3) · SQLAlchemy + psycopg2 (RDS) · Plotly · python-dotenv.

---

## 3. Méthodologie détaillée

### 3.1 Géocodage (Nominatim)
Chaque ville est convertie en coordonnées GPS via Nominatim (OpenStreetMap) : gratuit, sans
clé API, précision suffisante pour des villes françaises connues. Contrainte respectée :
1 requête/seconde. Résultat : **35/35 villes géocodées** → `cities_coords.csv`.

### 3.2 Météo (OpenWeather Forecast API)
Pour chaque ville, l'API renvoie des prévisions par tranches de 3 h sur 5 jours (40 points).
On les agrège **par jour** : température min/max, humidité moyenne, probabilité de pluie,
volume de pluie, vent. Résultat : **175 lignes** (5 j × 35 villes) → `weather_daily_detail.csv`.

### 3.3 Score météo et classement
Score composite normalisé 0–100 combinant 4 critères :

| Critère | Poids | Sens |
|---|---|---|
| Température max moyenne | 40 % | plus haut = mieux |
| Probabilité de pluie | 30 % | plus bas = mieux (inversé) |
| Volume total de pluie | 20 % | plus bas = mieux (inversé) |
| Humidité moyenne | 10 % | plus bas = mieux (inversé) |

Chaque variable est normalisée (min-max) puis pondérée. Pondération **arbitraire mais
documentée et défendable** ; en production, ces poids seraient appris à partir de données
comportementales (clics, réservations). Résultat → `weather_cities.csv` (35 villes classées).

### 3.4 Scraping des hôtels (Selenium + BeautifulSoup)
Booking.com est un site **dynamique** (contenu généré par JavaScript) : `requests.get()` ne
suffit pas. On pilote un vrai Chrome headless avec Selenium, on récupère ~20 hôtels par ville
(nom, URL, note, nombre d'avis), puis on parse le HTML rendu avec BeautifulSoup. Les points
étant tous positionnés sur le centre-ville, on les disperse légèrement (bruit ±0,02°) pour la
lisibilité de la carte. Résultat : **679 hôtels** → `hotels_booking.csv`.

### 3.5 Data Lake S3
Les 4 CSV sont uploadés sur `s3://kayak-jedha-aymeric/raw/` via boto3. Convention de préfixe
`raw/` pour les données brutes (extensible à `processed/`, `warehouse_ready/`).

### 3.6 ETL vers RDS PostgreSQL
- **Extract** : relecture des CSV depuis S3 (valide le pipeline cloud-only).
- **Transform** : sélection des colonnes utiles, typage, arrondis.
- **Load** : insertion dans 2 tables PostgreSQL via SQLAlchemy —
  `cities_weather` (35 lignes, PK `city_id`) et `hotels` (679 lignes, FK `city_id`).

Instance : `db.t3.micro`, PostgreSQL 16, région `eu-west-3`, free tier.

### 3.7 Visualisation (Plotly)
Deux cartes interactives (zoom, hover) exportées en HTML autonome :
`map_destinations.html` (35 villes + étoiles Top 5) et `map_hotels.html` (Top 20 hôtels).

---

## 4. Résultats

### Top 5 destinations (score météo /100)

| # | Ville | Temp. max moy. | Score |
|---|-------|---------------|-------|
| 1 | Aix-en-Provence | 16,3 °C | 88,9 |
| 2 | Avignon | 17,5 °C | 87,8 |
| 3 | Marseille | 15,8 °C | 86,7 |
| 4 | Paris | 15,6 °C | 85,5 |
| 5 | Grenoble | 16,5 °C | 82,3 |

Dominante Sud / Sud-Est, cohérente avec une fenêtre de 5 jours favorable au pourtour
méditerranéen.

### Chiffres clés

| Indicateur | Valeur |
|---|---|
| Villes géocodées | 35 / 35 |
| Mesures météo | 175 (5 j × 35 villes) |
| Hôtels scrapés | 679 (dont 216 avec une note Booking) |
| Objets sur S3 | 4 CSV (`raw/`) — ~157 KB |
| Lignes en RDS | 35 (`cities_weather`) + 679 (`hotels`) |
| Coût AWS | 0 € (free tier) → ~13 €/mois après |

---

## 5. Preuve de l'infrastructure cloud

Les notebooks sont livrés **exécutés avec leurs sorties**. Le notebook 1 contient :
- la **preuve S3** : listing du bucket via `boto3.list_objects_v2` (les 4 objets `raw/`) ;
- la **preuve RDS** : création des tables puis requêtes `SELECT` (Top 5 villes + Top 5 hôtels)
  lues directement depuis PostgreSQL.

Les credentials sont lus depuis `.env` (python-dotenv) et ne sont jamais commités. Les
étapes cloud sont encadrées par `try/except` : si les ressources AWS venaient à être
**dé-provisionnées après la formation** (pour éviter les coûts), les notebooks basculent sur
les CSV locaux sans planter, et l'architecture reste documentée ici.

---

## 6. Limites assumées

- **Champ `description` des hôtels** : les *property-cards* Booking n'exposent pas d'adresse
  fiable (`data-testid="address"` souvent absent). Plutôt que d'inventer une adresse, le champ
  est **renseigné à partir des données réellement collectées** (ville + note + nombre d'avis),
  ce qui donne une description lisible pour les 679 hôtels. La donnée d'adresse brute reste une
  limite du scraping.
- **Score météo sur 5 jours** : pas de saisonnalité — un séjour d'été et d'hiver sont traités
  identiquement.
- **Pondération du score** : arbitraire, non validée par des données comportementales.
- **Pas de prix hôtels** dans le score : un utilisateur pourrait préférer une ville moins chère.
- **Fragilité du scraping** : les sélecteurs CSS de Booking changent régulièrement.
- **Sécurité** : le Security Group RDS est ouvert (`0.0.0.0/0`) pour le bootcamp ; en prod on
  restreindrait à des IP fixes / un bastion, et on utiliserait un rôle IAM au lieu de `.env`.

---

## 7. Pour aller plus loin (production)

1. **Orchestration** : Airflow / Step Functions pour un rafraîchissement quotidien.
2. **Sécurité** : rôle IAM attaché à EC2, Security Group restreint, secrets en Secrets Manager.
3. **Robustesse** : retry exponentiel sur les appels API, alerting CloudWatch.
4. **Score** : poids appris depuis les réservations réelles ; intégrer le prix et la saison.
5. **Tests** : unitaires sur le parsing, end-to-end sur le pipeline.
6. **Périmètre** : étendre au-delà des 35 villes (Europe, monde).
