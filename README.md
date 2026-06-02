# LogMonitor Dashboard

> Plateforme SaaS professionnelle de gestion et monitoring de logs en temps réel.

---

## Présentation

**LogMonitor Dashboard** est une application web de monitoring de logs conçue pour les équipes DevOps et SRE. Elle centralise vos logs d'infrastructure, détecte les anomalies en temps réel et permet une réaction rapide avant que vos utilisateurs ne soient impactés.

---

## Stack Technique

| Composant | Technologie |
|---|---|
| **Backend** | Python 3.11+ · Django 5.0 |
| **Base de données** | PostgreSQL 15+ (SQLite en dev) |
| **Frontend** | Tailwind CSS · HTMX · Django Templates |
| **Graphiques** | Chart.js 4 |
| **Fonts** | Inter (UI) · JetBrains Mono (code/data) |
| **Serveur** | Gunicorn · WhiteNoise (static) |

---

## Architecture du Projet

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
│   │   ├── models.py            # User custom (rôles: admin/analyst/viewer/user)
│   │   ├── forms.py             # LoginForm, RegisterForm, UserAdminCreateForm, UserAdminEditForm
│   │   ├── views.py             # LoginView, LogoutView, RegisterView (CBV)
│   │   ├── profile.py           # ProfileView, PasswordChangeView
│   │   ├── user_management.py   # UserListView, UserCreateView, UserEditView, UserDeleteView
│   │   ├── mixins.py            # MonitoringOnlyMixin, AdminOnlyMixin (RBAC)
│   │   ├── urls.py
│   │   └── tests.py             # Tests unitaires
│   │
│   ├── logs/                    # Modèles & vues des logs
│   │   ├── models.py            # LogEntry, LogSource (indexés)
│   │   ├── views.py             # LogListView, LogDetailView (CBV)
│   │   ├── urls.py
│   │   ├── tests.py             # Tests unitaires
│   │   └── management/commands/
│   │       └── seed_data.py     # Génération de données de test
│   │
│   ├── dashboard/               # Dashboard principal
│   │   ├── views.py             # DashboardView, endpoints HTMX
│   │   ├── urls.py
│   │   ├── context_processors.py
│   │   └── tests.py             # Tests unitaires
│   │
│   ├── alerts/                  # Système d'alertes
│   │   ├── models.py            # Alert (sévérité, statut, RBAC)
│   │   ├── urls.py
│   │   └── apps.py
│   │
│   ├── servers/                 # Monitoring des serveurs
│   │   ├── models.py
│   │   ├── views.py             # ServerListView (avec MonitoringOnlyMixin)
│   │   └── urls.py
│   │
│   └── services/                # Monitoring des services
│       ├── models.py
│       ├── views.py             # ServiceListView (avec MonitoringOnlyMixin)
│       └── urls.py
│
├── templates/
│   ├── base.html                # Layout principal dark theme
│   ├── components/
│   │   ├── sidebar.html         # Navigation avec badges et contrôle RBAC
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

## Installation

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

## Lancement

```bash
python manage.py runserver
```

Accédez à : **http://localhost:8000**

| Page | URL |
|---|---|
| Connexion | `/auth/login/` |
| Inscription | `/auth/register/` |
| Dashboard | `/dashboard/` |
| Logs | `/logs/` |
| Alertes | `/alerts/` |
| Serveurs | `/servers/` |
| Services | `/services/` |
| Profil | `/auth/profile/` |
| Gestion utilisateurs *(admin)* | `/auth/users/` |

---

## Authentification & Comptes

### Connexion
- Page de connexion : `/auth/login/`
- Option "Se souvenir de moi" (session 30 jours)
- Bouton d'accès direct à l'inscription

### Inscription
- Page d'inscription : `/auth/register/`
- Formulaire : Prénom, Nom, Adresse email, Fuseau horaire, Mot de passe
- Connexion automatique après création du compte
- Rôle attribué par défaut : **Utilisateur**

### Compte démo
```
Identifiant : admin
Mot de passe : password123
```

---

## Rôles utilisateur (RBAC)

| Rôle | Pages accessibles | Création |
|---|---|---|
| **Administrateur** | Toutes les pages + Gestion des utilisateurs | Via admin ou formulaire |
| **Analyste** | Dashboard, Logs, Alertes, Serveurs, Services, Paramètres | Via admin |
| **Lecteur** | Dashboard, Logs, Alertes, Serveurs, Services, Paramètres | Via admin |
| **Utilisateur** | Dashboard, Logs, Alertes, Paramètres uniquement | Via inscription publique |

### Restrictions RBAC
- Le rôle **Utilisateur** ne voit pas la section Infrastructure (Serveurs / Services) dans la sidebar
- L'accès direct aux URLs `/servers/` et `/services/` par un Utilisateur redirige vers le Dashboard
- La page **Gestion des utilisateurs** `/auth/users/` est réservée aux Administrateurs
- Le compte `admin` par défaut est protégé : son rôle ne peut pas être modifié et il ne peut pas être supprimé

### Mixins RBAC disponibles
```python
# apps/accounts/mixins.py
MonitoringOnlyMixin   # Bloque le rôle 'user' (Utilisateur)
AdminOnlyMixin        # Réserve l'accès aux admins uniquement
```

---

## Gestion des utilisateurs (Admin)

Accessible à `/auth/users/` pour les comptes avec le rôle **Administrateur**.

| Fonctionnalité | Description |
|---|---|
| **Liste** | Tableau de tous les comptes avec rôle, email, date d'inscription, statut |
| **Créer** | Formulaire modal — champs : Prénom, Nom, Email, Fuseau, Rôle, Mot de passe |
| **Modifier** | Modal pré-rempli — modification du rôle (Utilisateur ↔ Administrateur) |
| **Supprimer** | Confirmation modale — suppression individuelle ou groupée |
| **Protection** | Le compte `admin` est protégé : rôle non modifiable, suppression impossible |

---

## Tests

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
python manage.py test apps.accounts
python manage.py test apps.logs
python manage.py test apps.dashboard
```

---

## Sécurité

- **Authentification Django** (AbstractUser customisé)
- **Protection CSRF** active sur tous les formulaires
- **Protection XSS** via Django templates (auto-escaping)
- **Session sécurisée** : expire à fermeture (sans remember me)
- **Logout POST-only** (Django 5 — protection contre CSRF logout)
- **RBAC** : Admin / Analyst / Viewer / User avec mixins dédiés
- **Headers de sécurité** : XFrame, XSS filter, HSTS (production)
- **Compte admin protégé** : impossible à supprimer ou à déclasser via l'interface

---

## Performance

- **select_related** sur toutes les requêtes avec FK (évite N+1)
- **bulk_create** pour l'ingestion de logs en volume
- **Index PostgreSQL** : `timestamp`, `level`, `(level, timestamp)`, `(source, timestamp)`
- **Pagination** : 50 logs/page (configurable via `LOGS_PER_PAGE`)
- **HTMX** : chargement asynchrone sans rechargement de page
- **Auto-refresh** : tableau des logs toutes les 30s (HTMX polling)

---

## HTMX — Interactions dynamiques

| Interaction | Endpoint | Trigger |
|---|---|---|
| Recherche temps réel | `GET /dashboard/htmx/recent-logs/` | keyup delay 400ms |
| Filtre niveau | `GET /dashboard/htmx/recent-logs/` | change |
| Auto-refresh table | `GET /dashboard/htmx/recent-logs/` | every 30s |
| Graphique période | `GET /dashboard/htmx/chart/volume/` | click bouton |
| Filtres logs | `GET /logs/` | change / keyup |

---

## Commandes utiles

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

# Vérifier la configuration Django
python manage.py check

# Shell interactif
python manage.py shell_plus  # (nécessite django-extensions)

# Collecter les statics (production)
python manage.py collectstatic --noinput
```

---

## Commandes de lancement rapide

```bash
# Activer l'environnement virtuel
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/macOS

# Dépendances Python

```bash
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate

# Charger les données de démonstration
python manage.py seed_data --logs 1000

# Lancer le serveur
python manage.py runserver
# → http://127.0.0.1:8000/
```

Naviguer dans l'interface :
- **Login** : http://localhost:8000/auth/login/ — `admin / password123`
- **Inscription** : http://localhost:8000/auth/register/
- **Gestion des utilisateurs** : http://localhost:8000/auth/users/ *(admin uniquement)*

---

## Roadmap

### Phase 1 (complétée)
- [x] Authentification & RBAC (Admin / Analyste / Lecteur / Utilisateur)
- [x] Inscription publique avec rôle Utilisateur par défaut
- [x] Dashboard KPIs + Graphique de volume
- [x] Explorateur de logs avec filtres HTMX
- [x] Détail d'un log avec traceback
- [x] Page Serveurs avec métriques
- [x] Page Services avec statuts
- [x] Gestion des utilisateurs (CRUD admin)
- [x] Sidebar adaptative selon le rôle

### Phase 2
- [ ] Système d'alertes complet (règles, seuils)
- [ ] API REST pour ingestion de logs

### Phase 3
- [ ] Notifications email/webhook
- [ ] Export CSV/JSON
- [ ] Dashboard multi-environnements
- [ ] Rate limiting & throttling

---

## Licence

Propriétaire — Gloire BOBOTI / Groupe 1 projet log 2025
Propriétaire LogMonitor Dashboard © 2025
