# LogMonitor Dashboard

> Plateforme SaaS professionnelle de gestion et monitoring de logs en temps réel.

---

## 🧩 Présentation

**LogMonitor Dashboard** est une application web de monitoring de logs conçue pour les équipes DevOps et SRE. Elle centralise vos logs d'infrastructure, détecte les anomalies en temps réel et permet une réaction rapide avant que vos utilisateurs ne soient impactés.

---

## ⚡ Stack Technique

| Composant | Technologie |
|---|---|
| **Backend** | Python 3.11+ · Django 5.0 |
| **Base de données** | PostgreSQL 15+ (SQLite en dev) |
| **Frontend** | Tailwind CSS · HTMX · Django Templates |
| **Graphiques** | Chart.js 4 |
| **Fonts** | Inter (UI) · JetBrains Mono (code/data) |
| **Serveur** | Gunicorn · WhiteNoise (static) |

---

## 🏗️ Architecture du Projet

```
logmonitor/
├── manage.py
├── requirements.txt
├── .env.example
├── logmonitor/                  # Configuration Django
│   ├── settings/
│   │   ├── base.py              # Paramètres communs
│   │   └── development.py      # Paramètres dev
│   ├── urls.py                  # URLs racines
│   └── wsgi.py
│
├── apps/
│   ├── accounts/                # Authentification & RBAC
│   │   ├── models.py            # User custom (rôles: admin/analyst/viewer)
│   │   ├── forms.py             # LoginForm
│   │   ├── views.py             # LoginView, LogoutView (CBV)
│   │   ├── urls.py
│   │   └── tests.py             # 11 tests unitaires
│   │
│   ├── logs/                    # Modèles & vues des logs
│   │   ├── models.py            # LogEntry, LogSource (indexés)
│   │   ├── views.py             # LogListView, LogDetailView (CBV)
│   │   ├── urls.py
│   │   ├── tests.py             # 17 tests unitaires
│   │   └── management/commands/
│   │       └── seed_data.py     # Génération de données de test
│   │
│   ├── dashboard/               # Dashboard principal
│   │   ├── views.py             # DashboardView, endpoints HTMX
│   │   ├── urls.py
│   │   ├── context_processors.py
│   │   └── tests.py             # 16 tests unitaires
│   │
│   └── alerts/                  # Système d'alertes
│       ├── models.py            # Alert (sévérité, statut, RBAC)
│       ├── urls.py
│       └── apps.py
│
├── templates/
│   ├── base.html                # Layout principal dark theme
│   ├── components/
│   │   ├── sidebar.html         # Navigation avec badges
│   │   └── header.html          # Header avec recherche HTMX
│   ├── partials/
│   │   └── log_table_rows.html  # Partial HTMX auto-refresh
│   └── dashboard/
│       └── index.html           # Dashboard KPIs + Chart.js + Table
│
└── static/
    ├── css/
    └── js/
```

---

## 🚀 Installation

### Prérequis

- Python 3.11+
- PostgreSQL 15+ (ou SQLite pour développement rapide)
- Node.js (optionnel, pour le build Tailwind en production)

### 1. Cloner le projet

```bash
git clone https://github.com/votre-repo/logmonitor.git
cd logmonitor
```

### 2. Environnement virtuel

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Dépendances Python

```bash
pip install -r requirements.txt
```

### 4. Variables d'environnement

```bash
cp .env.example .env
# Éditez .env avec vos paramètres
```

Paramètres minimum pour démarrer :

```env
SECRET_KEY=votre-secret-key-ici
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

Pour générer une `SECRET_KEY` sécurisée :
```bash
python -c "import secrets; print(secrets.token_hex(50))"
```

### 5. Base de données

```bash
python manage.py migrate
```

### 6. Données de démonstration

```bash
python manage.py seed_data --logs 1000
```

Génère :
- 10 sources (serveurs, services, DB…)
- 1000 logs réalistes sur 48h
- 2 alertes actives
- Compte admin : `admin / password123`

---

## ▶️ Lancement

```bash
python manage.py runserver
```

Accédez à : **http://localhost:8000**

- Page de login → `/auth/login/`
- Dashboard → `/dashboard/`
- Logs → `/logs/`

---

## 🧪 Tests

### Lancer tous les tests

```bash
python manage.py test
```

### Tests avec couverture

```bash
coverage run manage.py test
coverage report --show-missing
coverage html  # Rapport HTML dans htmlcov/
```

### Tests par app

```bash
python manage.py test apps.accounts   # 11 tests
python manage.py test apps.logs       # 17 tests
python manage.py test apps.dashboard  # 16 tests
```

---

## 🔐 Sécurité

- **Authentification Django** (AbstractUser customisé)
- **Protection CSRF** active sur tous les formulaires
- **Protection XSS** via Django templates (auto-escaping)
- **Session sécurisée** : expire à fermeture (sans remember me)
- **Logout POST-only** (Django 5 — protection contre CSRF logout)
- **RBAC** : Admin / Analyst / Viewer
- **Headers de sécurité** : XFrame, XSS filter, HSTS (production)

---

## ⚡ Performance

- **select_related** sur toutes les requêtes avec FK (évite N+1)
- **bulk_create** pour l'ingestion de logs en volume
- **Index PostgreSQL** : `timestamp`, `level`, `(level, timestamp)`, `(source, timestamp)`
- **Pagination** : 50 logs/page (configurable via `LOGS_PER_PAGE`)
- **HTMX** : chargement asynchrone sans rechargement de page
- **Auto-refresh** : tableau des logs toutes les 30s (HTMX polling)

---

## 🔁 HTMX — Interactions dynamiques

| Interaction | Endpoint | Trigger |
|---|---|---|
| Recherche temps réel | `GET /dashboard/htmx/recent-logs/` | keyup delay 400ms |
| Filtre niveau | `GET /dashboard/htmx/recent-logs/` | change |
| Auto-refresh table | `GET /dashboard/htmx/recent-logs/` | every 30s |
| Graphique période | `GET /dashboard/htmx/chart/volume/` | click bouton |
| Filtres logs | `GET /logs/` | change / keyup |

---

## 📋 Commandes utiles

```bash
# Créer un superuser
python manage.py createsuperuser

# Générer des données de test
python manage.py seed_data --logs 2000

# Vider et régénérer les données
python manage.py seed_data --logs 1000 --clear

# Migrations
python manage.py makemigrations
python manage.py migrate

# Shell interactif
python manage.py shell_plus  # (nécessite django-extensions)

# Collecter les statics (production)
python manage.py collectstatic --noinput
```

---

## 🗺️ Roadmap

### Phase 1 (actuelle)
- [x] Authentification & RBAC
- [x] Dashboard KPIs + Graphique de volume
- [x] Explorateur de logs avec filtres HTMX
- [x] Détail d'un log avec traceback

### Phase 2
- [ ] Système d'alertes complet (règles, seuils)
- [ ] Page Serveurs avec métriques
- [ ] Page Services avec statuts
- [ ] API REST pour ingestion de logs

### Phase 3
- [ ] Notifications email/webhook
- [ ] Export CSV/JSON
- [ ] Dashboard multi-environnements
- [ ] Rate limiting & throttling

---

## 👥 Rôles utilisateur (RBAC)

| Rôle | Accès |
|---|---|
| **Admin** | Tout + administration Django |
| **Analyst** | Dashboard, logs, alertes — lecture/écriture |
| **Viewer** | Dashboard, logs — lecture seule |

---

## Commandes de lancement rapide

Activer l'environnement virtuel
venv/Scripts/activate

Appliquer les migrations (si ce n'est pa encore fait)
python manage.py migrate

Charger les données (si ce n'est pas encore fait)
python manage.py seed_data --logs 1000

Lancer le serveur
python manage.py runserver

output terminal : Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C

-
Naviguer dans l'interface
http://localhost:8000/auth/login/

id: admin
mdp: password123

---

## 📄 Licence

Propriétaire — Gloire BOBOTI/ Groupe 1 projet log 2025
Propriètaire LogMonitor Dashboard © 2025
