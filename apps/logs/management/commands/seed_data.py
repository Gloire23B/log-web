"""
apps/logs/management/commands/seed_data.py
─────────────────────────────────────────────────────────────────
Commande de peuplement pour le développement.
Génère des données réalistes pour tester l'interface.

Usage :
    python manage.py seed_data
    python manage.py seed_data --logs 5000
    python manage.py seed_data --clear
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Peuple la base de données avec des données de développement réalistes"

    def add_arguments(self, parser):
        parser.add_argument("--logs", type=int, default=500,
                            help="Nombre de logs à générer (défaut: 500)")
        parser.add_argument("--clear", action="store_true",
                            help="Vider les données existantes avant insertion")

    def handle(self, *args, **options):
        from apps.logs.models import LogEntry, LogSource
        from apps.alerts.models import Alert

        if options["clear"]:
            self.stdout.write("🗑️  Suppression des données existantes…")
            LogEntry.objects.all().delete()
            LogSource.objects.all().delete()
            Alert.objects.all().delete()

        # ── Création des sources ──────────────────────────────────────────
        self.stdout.write("📡 Création des sources…")
        sources_data = [
            ("api-gateway", LogSource.SourceType.SERVICE, "10.0.0.1"),
            ("auth-service", LogSource.SourceType.SERVICE, "10.0.0.2"),
            ("prod-db-primary", LogSource.SourceType.DATABASE, "10.0.1.1"),
            ("prod-db-replica", LogSource.SourceType.DATABASE, "10.0.1.2"),
            ("web-server-01", LogSource.SourceType.SERVER, "10.0.2.1"),
            ("web-server-02", LogSource.SourceType.SERVER, "10.0.2.2"),
            ("worker-queue", LogSource.SourceType.APPLICATION, "10.0.3.1"),
            ("cdn-proxy", LogSource.SourceType.NETWORK, "10.0.4.1"),
            ("monitoring-agent", LogSource.SourceType.APPLICATION, "10.0.5.1"),
            ("firewall", LogSource.SourceType.SECURITY, "10.0.0.254"),
        ]
        sources = []
        for name, stype, hostname in sources_data:
            src, _ = LogSource.objects.get_or_create(
                name=name,
                defaults={"source_type": stype, "hostname": hostname}
            )
            sources.append(src)

        # ── Génération des logs ───────────────────────────────────────────
        log_count = options["logs"]
        self.stdout.write(f"📝 Génération de {log_count} logs…")

        messages = {
            LogEntry.Level.DEBUG: [
                "Cache invalidated for key user:{id}",
                "SQL query executed in {ms}ms: SELECT * FROM logs WHERE...",
                "Request headers: Accept: application/json",
                "Session token refreshed for user {id}",
                "Background task started: cleanup_old_sessions",
                "Config loaded: DEBUG=True, DB_POOL=10",
            ],
            LogEntry.Level.INFO: [
                "GET /api/v2/users 200 OK ({ms}ms)",
                "POST /api/v2/auth/login 200 OK — user {id} authenticated",
                "Job queue processed {n} tasks in {ms}ms",
                "Database connection established to prod-db-primary",
                "Health check passed — all services operational",
                "Scheduled backup completed: 2.3GB in 45s",
                "New deployment detected: v2.1.{n} → v2.1.{n2}",
                "SSL certificate renewed — expires in 90 days",
            ],
            LogEntry.Level.WARNING: [
                "Slow query detected ({ms}ms): SELECT COUNT(*) FROM log_entries",
                "Memory usage at 78% — threshold: 80%",
                "Connection pool near capacity: {n}/100",
                "Retry #{n} for external API call to payment-service",
                "Rate limit approaching for client 192.168.1.{n}: 450/500 req/min",
                "Disk usage at 68% on /var/log partition",
                "High CPU load average: {f} (threshold: 2.0)",
            ],
            LogEntry.Level.ERROR: [
                "Connection timeout to redis:6379 after 5000ms",
                "Database query failed: deadlock detected on table log_entries",
                "HTTP 503 received from payment-service: Service Unavailable",
                "Failed to send email notification: SMTP authentication failed",
                "JWT token validation failed: signature mismatch",
                "File upload failed: disk quota exceeded",
                "Worker process {id} crashed with exit code 1",
                "API rate limit exceeded for external service",
            ],
            LogEntry.Level.CRITICAL: [
                "CRITICAL: Disk usage above 95% threshold — immediate action required",
                "CRITICAL: Database primary node unreachable — failover initiated",
                "CRITICAL: Memory OOM killer activated — process killed",
                "CRITICAL: SSL certificate expires in 2 days",
                "CRITICAL: 500+ errors/min detected — potential DDoS",
            ],
        }

        # Distribution réaliste des niveaux
        level_weights = {
            LogEntry.Level.DEBUG: 20,
            LogEntry.Level.INFO: 50,
            LogEntry.Level.WARNING: 20,
            LogEntry.Level.ERROR: 8,
            LogEntry.Level.CRITICAL: 2,
        }

        levels = list(level_weights.keys())
        weights = list(level_weights.values())
        now = timezone.now()

        batch = []
        for i in range(log_count):
            level = random.choices(levels, weights=weights, k=1)[0]
            template = random.choice(messages[level])
            msg = template.format(
                id=random.randint(1000, 9999),
                ms=random.randint(10, 5000),
                n=random.randint(1, 100),
                n2=random.randint(1, 100),
                f=round(random.uniform(0.5, 4.5), 2),
            )
            batch.append(LogEntry(
                timestamp=now - timedelta(
                    hours=random.uniform(0, 48),
                    minutes=random.uniform(0, 60),
                ),
                level=level,
                message=msg,
                source=random.choice(sources),
                logger_name=random.choice([
                    "django.request", "django.db", "apps.logs.views",
                    "celery.worker", "gunicorn.error", "apps.auth", "",
                ]),
                traceback="Traceback (most recent call last):\n  File 'apps/views.py', line 42\nConnectionError: timeout" if level in (LogEntry.Level.ERROR, LogEntry.Level.CRITICAL) and random.random() > 0.5 else "",
            ))

        # Insertion en batch pour les performances
        LogEntry.objects.bulk_create(batch, batch_size=200)

        # ── Création du superuser ─────────────────────────────────────────
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@logmonitor.io",
                password="password123",
                first_name="Admin",
                last_name="LogMonitor",
                role=User.Role.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS("👤 Superuser créé : admin / password123"))

        # ── Alertes de démo ──────────────────────────────────────────────
        if Alert.objects.count() == 0:
            Alert.objects.create(
                title="Disk usage critique sur prod-db-primary",
                severity=Alert.Severity.CRITICAL,
                status=Alert.Status.ACTIVE,
                source=next(s for s in sources if "db" in s.name),
                description="L'espace disque dépasse 95% sur le nœud principal.",
            )
            Alert.objects.create(
                title="Ralentissements détectés sur api-gateway",
                severity=Alert.Severity.HIGH,
                status=Alert.Status.ACTIVE,
                source=next(s for s in sources if "api" in s.name),
                description="Temps de réponse moyen > 2000ms depuis 15 minutes.",
            )

        # ── Serveurs de démo ─────────────────────────────────────────
        from apps.servers.models import Server
        if Server.objects.count() == 0:
            self.stdout.write("🖥️  Création des serveurs…")
            servers_demo = [
                ("prod-web-01", "web-01.prod.internal", "10.0.2.1",
                 Server.Environment.PRODUCTION, 72.3, 68.1, 41.2, Server.Status.ONLINE),
                ("prod-web-02", "web-02.prod.internal", "10.0.2.2",
                 Server.Environment.PRODUCTION, 81.5, 74.0, 43.8, Server.Status.WARNING),
                ("prod-db-primary", "db-01.prod.internal", "10.0.1.1",
                 Server.Environment.PRODUCTION, 45.2, 82.3, 91.7, Server.Status.CRITICAL),
                ("prod-db-replica", "db-02.prod.internal", "10.0.1.2",
                 Server.Environment.PRODUCTION, 38.1, 71.5, 44.1, Server.Status.ONLINE),
                ("staging-app-01", "app-01.staging", "10.1.2.1",
                 Server.Environment.STAGING, 22.4, 55.6, 30.2, Server.Status.ONLINE),
                ("dev-server-01", "dev-01.local", "10.2.0.1",
                 Server.Environment.DEVELOPMENT, 15.8, 40.2, 25.0, Server.Status.ONLINE),
            ]
            for name, hostname, ip, env, cpu, mem, disk, status in servers_demo:
                src = next((s for s in sources if name.split("-")[1] in s.name or name in s.name), None)
                Server.objects.create(
                    name=name, hostname=hostname, ip_address=ip,
                    environment=env, status=status,
                    cpu_percent=cpu, memory_percent=mem, disk_percent=disk,
                    uptime_seconds=random.randint(3600, 86400 * 60),
                    last_seen=now - timezone.timedelta(seconds=random.randint(10, 120)),
                    log_source=src,
                )

        # ── Services de démo ─────────────────────────────────────────
        from apps.services.models import Service
        if Service.objects.count() == 0:
            self.stdout.write("⚙️  Création des services…")
            services_demo = [
                ("api-gateway",   "API Gateway",       Service.ServiceType.API,
                 Service.Status.OPERATIONAL,  "v3.2.1", 142.5, 0.12, 1250.0, 99.98),
                ("auth-service",  "Auth Service",      Service.ServiceType.API,
                 Service.Status.DEGRADED,     "v1.8.0",  890.3,  2.41,  320.0, 99.71),
                ("worker-queue",  "Worker Queue",      Service.ServiceType.WORKER,
                 Service.Status.OPERATIONAL,  "v2.1.0",  55.2,  0.03,   87.5, 100.0),
                ("cache-redis",   "Redis Cache",       Service.ServiceType.CACHE,
                 Service.Status.OPERATIONAL,  "7.2.4",   12.1,  0.01, 9500.0, 100.0),
                ("db-primary",    "PostgreSQL Primary",Service.ServiceType.DATABASE,
                 Service.Status.OPERATIONAL,  "15.3",    38.7,  0.05,  245.0, 99.99),
                ("cdn-proxy",     "CDN Proxy",         Service.ServiceType.PROXY,
                 Service.Status.MAINTENANCE,  "v1.5.2",  None,   None,    None,  None),
                ("scheduler",     "Job Scheduler",     Service.ServiceType.SCHEDULER,
                 Service.Status.OPERATIONAL,  "v0.9.3",  28.4,  0.00,   12.0, 100.0),
            ]
            for (name, display, stype, status, version,
                 latency, err_rate, rps, uptime) in services_demo:
                src = next((s for s in sources if name in s.name), None)
                Service.objects.create(
                    name=name, display_name=display, service_type=stype,
                    status=status, version=version,
                    avg_latency_ms=latency, error_rate=err_rate,
                    requests_per_sec=rps, uptime_30d=uptime,
                    last_check=now - timezone.timedelta(seconds=random.randint(5, 60)),
                    log_source=src,
                )

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Données générées avec succès :\n"
            f"   • {len(sources)} sources\n"
            f"   • {log_count} logs\n"
            f"   • {Server.objects.count()} serveurs\n"
            f"   • {Service.objects.count()} services\n"
            f"   • {Alert.objects.count()} alertes\n"
            f"\n🚀 Connectez-vous avec : admin / password123"
        ))
