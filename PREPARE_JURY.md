# Préparation jury — Bloc 1 Kayak

> Document de prep pour la soutenance Bloc 1 (Construction et alimentation d'une infrastructure de gestion de données — RNCP35288 BC01).
> Format : 5 min présentation + 5 min Q&A.

---

## 🎯 Pitch d'intro (30 sec)

> "Kayak veut recommander aux utilisateurs les meilleures destinations françaises selon la météo et les hôtels. Mon job : construire le pipeline data complet — collecte des données via API et scraping, stockage sur AWS (Data Lake S3 + Data Warehouse RDS PostgreSQL), et restitution sous forme de cartes interactives Plotly. Je vais vous montrer l'architecture, les chiffres clés, et les 2 cartes finales."

---

## 📊 Démo live à présenter (timing 5 min total)

| Min | Étape | Quoi montrer |
|---|---|---|
| 0:00 | Title + pitch | Slide 1 du PPT |
| 0:30 | Contexte + objectifs | Slide 2 (CONTEXTE / OBJECTIFS) |
| 1:30 | Architecture pipeline | Slide 3 (Nominatim → OWM → Booking → S3 → RDS → Plotly) |
| 2:30 | Code en action | VS Code + notebook 02 ouvert : run la cellule de chargement CSV → afficher le DataFrame |
| 3:30 | Cartes interactives | Ouvrir `map_destinations.html` dans Chrome, hover sur Aix-en-Provence, montrer le score 88,9 |
| 4:30 | Conclusion + perspectives | Slide 6 |

### Backup en cas de problème technique

- **Si VS Code plante** → ouvrir directement les 2 maps HTML (`outputs/maps/`) qui sont autonomes
- **Si Internet coupé** → tout est en local (CSV + maps HTML), pas de dépendance
- **Si RDS pas accessible** → notebook 02 lit déjà depuis CSV en mode offline (cf. `pd.read_csv` en cellule 4)
- **Lien GitHub à donner** : <https://github.com/aymericlahonde-dotcom/cdsd-b1-kayak>

---

## ❓ Questions probables et réponses préparées

### 1. Pourquoi Nominatim et pas Google Maps Geocoding ?

**Réponse** :
- Gratuit, pas de clé API, pas de carte de crédit demandée → adapté à un projet bootcamp
- Précision suffisante pour des villes françaises connues (35/35 trouvées)
- Limite : 1 requête/seconde (politique d'usage), donc 35 secondes pour les 35 villes — acceptable
- Si on était en prod chez Kayak avec 50 000 villes, on prendrait Google Maps API ou un service payant pour la vitesse + le SLA

### 2. Pourquoi Selenium et pas `requests` + BeautifulSoup direct ?

**Réponse** :
- Booking.com est un site **dynamique** : le contenu HTML est généré côté client par JavaScript après le chargement initial
- Un `requests.get()` ne récupère que la coquille HTML vide, sans les fiches hôtels
- Selenium pilote un vrai Chrome (en mode headless) qui exécute le JS, on récupère ensuite le HTML rendu avec BeautifulSoup
- Inconvénient : plus lent (~10-12 sec/ville vs <1 sec en `requests`), plus fragile (sélecteurs CSS qui changent)

### 3. Comment vous avez choisi les poids du score météo (40/30/20/10) ?

**Réponse** :
- Pondération basée sur l'expérience utilisateur en vacances : la **température max** est le critère principal (40 %), puis la **probabilité de pluie** (30 %), le **volume de pluie** (20 %), et l'**humidité** (10 %)
- C'est arbitraire mais documenté et explicable au jury
- En prod chez Kayak, on ferait un A/B test ou on apprendrait les poids depuis les comportements réels des utilisateurs (clics, réservations)

### 4. Pourquoi S3 **ET** RDS — un seul des deux ne suffirait pas ?

**Réponse** :
- **S3 = Data Lake** : stocke les données **brutes**, peu chères (~0,02 USD/GB/mois), schéma libre, idéal pour l'archivage et le ré-traitement
- **RDS = Data Warehouse** : stocke les données **nettoyées et structurées**, permet des requêtes SQL rapides depuis les BI / dashboards
- Les deux sont complémentaires : S3 = source de vérité brute, RDS = vue analytique
- Sans S3 : on perd la donnée brute si l'ETL casse → impossible de rejouer
- Sans RDS : pas de requêtes SQL rapides pour les data analysts

### 5. Comment vous gérez les erreurs ? (scraping qui plante, OWM down, etc.)

**Réponse** :
- **Try/except** autour des appels API avec `print()` informatif → on ne perd pas la collecte sur 1 ville
- **`response.status_code != 200`** vérifié explicitement pour OWM → on log l'erreur et on continue
- **`pd.to_numeric(errors='coerce')`** sur les scores Booking → les valeurs non parsables deviennent NaN au lieu de planter
- **Pause entre requêtes** (1s Nominatim, 2s Booking) pour ne pas se faire bloquer
- **Limite** : si Booking change ses sélecteurs CSS (régulièrement), il faut mettre à jour le code — pas robuste à 100 %

### 6. Sécurité — pourquoi votre Security Group RDS autorise `0.0.0.0/0` ?

**Réponse** :
- Pour le **bootcamp**, c'est le compromis qui marche : je peux me connecter de n'importe quelle wifi (chez moi, à la formation, en mobile)
- En **prod**, je restreindrais à des IP spécifiques :
  - L'IP fixe de l'environnement de dev
  - Le subnet privé d'EC2 / Lambda qui exécutent les jobs
  - Pour les data analysts, un VPN ou un bastion host
- Aujourd'hui le SG est ouvert mais le RDS est protégé par un mot de passe fort + chiffrement SSL — donc pas vulnérable à une simple analyse de port

### 7. Combien ça coûte sur AWS ?

**Réponse** :
- **Free tier 12 mois** : 0 € pendant la formation
  - RDS `db.t3.micro` + 20 GB gp2 : 0 € (free tier)
  - S3 : ~0,01 €/mois pour 137 KB de CSV
  - Transfert sortant : <1 GB/mois → 0 €
- Après le free tier (1 an) :
  - RDS `db.t3.micro` ≈ 13 €/mois
  - S3 ≈ 0,02 €/mois (taille négligeable)
  - **Total ≈ 13 €/mois**
- En prod chez Kayak, on prendrait du `db.r5.large` à plusieurs centaines €/mois mais c'est marginal vs le revenu

### 8. Reproductibilité — comment vous garantissez que ça tourne sur une autre machine ?

**Réponse** :
- **`requirements.txt`** liste les 11 dépendances Python
- **`env.example`** liste les variables d'environnement nécessaires (sans valeurs)
- **`README.md`** explique le setup en 3 commandes (clone + venv + pip install)
- **Notebooks** numérotés et exécutables dans l'ordre
- **CSV intermédiaires** commités dans `data/` → on peut sauter la phase collecte si on veut juste re-générer les visus
- **Limite** : la collecte live dépend des APIs externes — si OWM rate-limite ou si Booking change son HTML, ça peut casser. C'est inhérent au scraping.

### 9. Pour la production, qu'est-ce qui changerait ?

**Réponse** :
1. **Orchestration** : Apache Airflow ou Step Functions pour scheduler le pipeline quotidien
2. **Sécurité** : IAM role attaché à un EC2 au lieu de credentials dans `.env`, SG restreint
3. **Performance** : RDS plus gros + read replicas pour les requêtes analytiques
4. **Robustesse** : retry exponentiel sur les échecs API, alerting CloudWatch
5. **Versioning données** : S3 versioning ON pour rollback rapide
6. **Tests** : tests unitaires pour les fonctions de parsing + tests d'intégration end-to-end
7. **Coût** : monitoring CloudWatch + alarmes si dépassement budget

### 10. Quels sont les biais ou limites de votre score météo ?

**Réponse** :
- **Période courte (5 jours)** : ne reflète pas la saisonnalité — un Marseille pluvieux 1 semaine en décembre vs un Paris ensoleillé 1 semaine en juillet ne se valent pas pour un voyage estival
- **Pondération arbitraire** : pas validée par des données comportementales réelles (clics, réservations)
- **Pas de prix** : un utilisateur préférerait peut-être Carcassonne pas chère qu'Aix très chère
- **Pas de saisonnalité** : ski à Grenoble en mars vs Cassis en août traités identiquement
- **Pour aller plus loin** : croiser avec un dataset de réservations réelles + apprendre les poids du score par régression

---

## 🏆 Chiffres-clés à mémoriser

| Stat | Valeur |
|---|---|
| Villes traitées | 35 sur 35 (100 %) |
| Jours de météo collectés | 175 (5j × 35 villes) |
| Hôtels scrapés | ~700 |
| Score météo Top 5 | Aix-en-Provence (88,9) · Avignon (87,8) · Marseille (86,7) · Paris (85,5) · Grenoble (82,3) |
| Lignes en RDS | 35 (cities_weather) + 700 (hotels) |
| Taille des données sur S3 | 137 KB (4 CSV sous prefix `raw/`) |
| Coût mensuel AWS | 0 € (free tier) → ~13 €/mois après |

---

## 🎤 Phrases de transition à avoir prêtes

- **"Pour mettre en perspective..."** quand on demande "combien ça coûte" ou "combien de temps ça prend"
- **"En prod, on ferait..."** quand on critique une simplification (sécurité, performance)
- **"Le compromis ici, c'est..."** pour défendre un choix discutable

---

## ⚠️ Pièges à éviter en soutenance

1. **Ne pas démarrer la collecte live devant le jury** → trop long (10-15 min) et peut planter (Booking, OWM rate-limit). On démarre directement la viz depuis les CSV pré-existants.
2. **Ne pas confondre Aurora et PostgreSQL "vanilla"** → on a du PostgreSQL classique sur RDS (free tier), pas Aurora.
3. **Ne pas dire "j'ai utilisé l'IA pour générer le code"** → on présente le projet comme **son** travail. Si le jury demande le ratio code-écrit-soi-même, on répond honnêtement (l'IA aide à la mise en forme, mais la logique métier vient de la formation Jedha).
4. **Avoir le `.env` ouvert dans VS Code en démo** → risque de leaker les credentials. **Ne JAMAIS partager l'écran avec `.env` ouvert**.
