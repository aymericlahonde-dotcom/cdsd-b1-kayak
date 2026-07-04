# Bloc 1 — Plan your trip with Kayak

> Projet de la **Certification Jedha — Concepteur Développeur en Science des Données (CDSD)**
> [RNCP35288 — France Compétences](https://www.francecompetences.fr/recherche/rncp/35288/)
> **Bloc 1** : Construction et alimentation d'une infrastructure de gestion de données (Data Engineering / ETL)

## Contexte

Kayak (groupe Booking Holdings) veut aider ses utilisateurs à choisir une destination :
une étude interne montre que 70 % des voyageurs veulent plus d'informations sur leur
destination avant de réserver. Aucune donnée n'existe au départ : il faut **construire tout
le pipeline** — collecte, stockage cloud, restitution — pour recommander les meilleures
villes françaises selon la **météo** et les **hôtels**.

Périmètre : les **35 plus belles villes françaises** listées par Kayak.

## Architecture du pipeline

```
Nominatim (geocoding)  →  OpenWeather (météo 5j)  →  Booking.com (Selenium + BS4)
        │                                                     │
        └──────────────►  CSV locaux (data/)  ◄──────────────┘
                                 │
                    AWS S3  (Data Lake — CSV bruts, prefix raw/)
                                 │
                    AWS RDS PostgreSQL  (Data Warehouse — tables nettoyées)
                                 │
                    Plotly Express  (2 cartes interactives HTML)
```

| Étape | Outil | Sortie |
|---|---|---|
| Géocodage | Nominatim (OpenStreetMap) | `data/cities_coords.csv` — 35 villes |
| Météo | OpenWeather Forecast API | `data/weather_daily_detail.csv` — 175 lignes (5j × 35) |
| Score & classement | pandas (score composite 0–100) | `data/weather_cities.csv` — 35 villes classées |
| Scraping hôtels | Selenium (Chrome headless) + BeautifulSoup | `data/hotels_booking.csv` — 679 hôtels |
| Data Lake | AWS S3 (boto3) | bucket `s3://kayak-jedha-aymeric/raw/` (4 CSV) |
| Data Warehouse | AWS RDS PostgreSQL 16 (SQLAlchemy) | tables `cities_weather` (35) + `hotels` (679) |
| Visualisation | Plotly Express | `outputs/maps/map_destinations.html` + `map_hotels.html` |

## Livrables

- **`notebooks/01_Data_Collection_Pipeline.ipynb`** — collecte, scoring, upload S3, ETL vers RDS (exécuté, avec sorties).
- **`notebooks/02_Visualization.ipynb`** — les 2 cartes interactives Plotly (exécuté, avec figures).
- **`outputs/maps/`** — les 2 cartes HTML autonomes (Top 5 destinations + Top 20 hôtels).
- **`Presentation_Kayak.pptx`** — support de soutenance jury (6 slides + notes).
- **`dossier_projet.md`** — rapport détaillé (contexte, méthodo, résultats, limites).

## Résultat — Top 5 destinations (score météo /100)

| # | Ville | Temp. max moy. | Score |
|---|-------|---------------|-------|
| 1 | Aix-en-Provence | 16,3 °C | 88,9 |
| 2 | Avignon | 17,5 °C | 87,8 |
| 3 | Marseille | 15,8 °C | 86,7 |
| 4 | Paris | 15,6 °C | 85,5 |
| 5 | Grenoble | 16,5 °C | 82,3 |

## Setup

```bash
# 1. Cloner le repo
git clone https://github.com/aymericlahonde-dotcom/cdsd-b1-kayak.git
cd cdsd-b1-kayak

# 2. Environnement Python 3.11
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash / .venv\Scripts\activate sous PowerShell
pip install -r requirements.txt

# 3. Variables d'environnement
cp env.example .env
#   puis renseigner OWM_API_KEY, AWS_ACCESS_KEY_ID/SECRET, S3_BUCKET, RDS_URI
```

Les notebooks tournent par défaut en mode **reproductible** (`RUN_LIVE_COLLECTION = False`) :
ils rechargent les CSV déjà présents dans `data/` au lieu de relancer la collecte live
(scraping Booking et appels API, lents et fragiles). Passer le flag à `True` pour rejouer
toute la collecte. Les étapes S3 / RDS sont encadrées par des `try/except` : elles produisent
une preuve réelle quand les ressources AWS répondent, et n'interrompent pas l'exécution sinon.

> Les secrets (`.env`) ne sont **jamais** commités. Voir `env.example` pour le format attendu.

## Auteur

[Aymeric Lahonde](https://github.com/aymericlahonde-dotcom) — promotion Jedha CDSD 2026.
Plateforme Jedha : <https://app.jedha.co/>
