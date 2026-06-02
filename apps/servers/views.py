"""
apps/servers/views.py
─────────────────────────────────────────────────────────────────
Vues de monitoring et gestion des serveurs.
"""
import io
import os
import re
import socket
import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.accounts.mixins import AdminOnlyMixin, MonitoringOnlyMixin
from .forms import ServerForm
from .models import Server


class ServerListView(MonitoringOnlyMixin, LoginRequiredMixin, ListView):
    """Grille de monitoring des serveurs avec métriques."""
    model = Server
    template_name = "servers/list.html"
    context_object_name = "servers"
    login_url = "/auth/login/"

    def get_queryset(self):
        return Server.objects.select_related("log_source").filter(
            is_active=True
        ).order_by("environment", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servers = context["servers"]

        status_counts = {s.value: 0 for s in Server.Status}
        for srv in servers:
            status_counts[srv.status] = status_counts.get(srv.status, 0) + 1

        by_env = {}
        for srv in servers:
            env = srv.get_environment_display()
            by_env.setdefault(env, []).append(srv)

        context.update({
            "page_title": "Serveurs — LogMonitor",
            "page_heading": "Serveurs",
            "status_counts": status_counts,
            "servers_by_env": by_env,
            "total": len(servers),
            "online_count": status_counts.get("online", 0),
            "critical_count": status_counts.get("critical", 0),
            "create_form": ServerForm(),
        })
        return context


class ServerCreateView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Création d'un serveur depuis l'interface."""
    login_url = "/auth/login/"

    def post(self, request):
        form = ServerForm(request.POST)
        if form.is_valid():
            server = form.save()
            messages.success(request, f"Serveur « {server.name} » ajouté avec succès.")
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect("servers:list")


class ServerEditView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Mise à jour d'un serveur existant."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        server = get_object_or_404(Server, pk=pk)
        form = ServerForm(request.POST, instance=server)
        if form.is_valid():
            form.save()
            messages.success(request, f"Serveur « {server.name} » mis à jour.")
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect("servers:list")


class ServerDeleteView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Suppression d'un serveur."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        server = get_object_or_404(Server, pk=pk)
        name = server.name
        server.delete()
        messages.success(request, f"Serveur « {name} » supprimé.")
        return redirect("servers:list")


class ServerCheckView(MonitoringOnlyMixin, LoginRequiredMixin, View):
    """
    Vérifie dynamiquement la connectivité TCP d'un serveur.
    Retourne le partial HTML de la carte (pour swap HTMX).
    """
    login_url = "/auth/login/"

    def post(self, request, pk):
        server = get_object_or_404(Server, pk=pk)
        ip = server.ip_address or server.hostname

        if not ip:
            server.status = Server.Status.UNKNOWN
            server.save(update_fields=["status"])
        else:
            reachable = False
            for port in [22, 80, 443, 8080]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                try:
                    result = sock.connect_ex((str(ip), port))
                    if result == 0:
                        reachable = True
                        break
                except (socket.timeout, socket.error, OSError):
                    pass
                finally:
                    sock.close()

            if reachable:
                server.last_seen = timezone.now()
                server.compute_status()
                server.save(update_fields=["status", "last_seen"])
            else:
                server.status = Server.Status.OFFLINE
                server.save(update_fields=["status"])

        return render(request, "servers/partials/card.html", {"server": server})


class ServerAgentScriptView(MonitoringOnlyMixin, LoginRequiredMixin, View):
    """
    Retourne le script agent (logmonitor_agent.py) en téléchargement,
    pré-configuré avec le nom du serveur et l'URL LogMonitor.
    """
    login_url = "/auth/login/"

    def get(self, request, pk):
        server = get_object_or_404(Server, pk=pk)
        base_url = request.build_absolute_uri("/").rstrip("/")

        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "logmonitor_agent.py",
        )
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            from django.http import Http404
            raise Http404("logmonitor_agent.py introuvable.")

        # Injecter les valeurs par défaut dans le script
        content = content.replace(
            'parser.add_argument("--url",      required=True,',
            f'parser.add_argument("--url",      default="{base_url}",',
            1,
        )
        content = content.replace(
            'parser.add_argument("--source",   required=True,',
            f'parser.add_argument("--source",   default="{server.name}",',
            1,
        )

        from django.http import HttpResponse
        response = HttpResponse(content, content_type="text/x-python")
        filename = f"logmonitor_agent_{server.name.replace(' ', '_')}.py"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ServerSSHCollectView(AdminOnlyMixin, LoginRequiredMixin, View):
    """
    Collecte les métriques et logs d'un serveur distant via SSH.
    Requiert paramiko : pip install paramiko
    """
    login_url = "/auth/login/"

    def post(self, request, pk):
        server = get_object_or_404(Server, pk=pk)

        ssh_user     = request.POST.get("ssh_user", "").strip()
        ssh_password = request.POST.get("ssh_password", "").strip()
        ssh_port     = int(request.POST.get("ssh_port", 22) or 22)
        log_lines    = int(request.POST.get("log_lines", 100) or 100)

        if not ssh_user:
            messages.error(request, "Le nom d'utilisateur SSH est obligatoire.")
            return redirect("servers:list")

        host = server.ip_address or server.hostname
        if not host:
            messages.error(request, f"Le serveur « {server.name} » n'a pas d'adresse IP ni de hostname.")
            return redirect("servers:list")

        try:
            import paramiko
        except ImportError:
            messages.error(request, "paramiko n'est pas installé. Exécutez : pip install paramiko")
            return redirect("servers:list")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                str(host),
                port=ssh_port,
                username=ssh_user,
                password=ssh_password or None,
                timeout=10,
                banner_timeout=10,
            )
        except paramiko.AuthenticationException:
            messages.error(request, f"Authentification SSH refusée pour {ssh_user}@{host}:{ssh_port}.")
            return redirect("servers:list")
        except (paramiko.SSHException, socket.error, OSError) as exc:
            messages.error(request, f"Impossible de se connecter à {host}:{ssh_port} — {exc}")
            return redirect("servers:list")

        try:
            metrics = self._collect_metrics_ssh(ssh)
            logs    = self._collect_logs_ssh(ssh, log_lines)
        finally:
            ssh.close()

        # ── Mettre à jour les métriques du serveur ───────────────────
        update_fields = ["last_seen", "status"]
        server.last_seen = timezone.now()
        for field, value in metrics.items():
            if value is not None:
                setattr(server, field, value)
                update_fields.append(field)
        server.compute_status()
        server.save(update_fields=list(set(update_fields)))

        # ── Créer les entrées de log ─────────────────────────────────
        from apps.logs.models import LogEntry, LogSource
        source, _ = LogSource.objects.get_or_create(
            name=server.name,
            defaults={"source_type": LogSource.SourceType.SERVER},
        )
        entries = []
        for raw in logs:
            entries.append(LogEntry(
                level=raw.get("level", "INFO"),
                message=raw.get("message", "")[:2000],
                source=source,
                logger_name="ssh.collector",
            ))
        if entries:
            LogEntry.objects.bulk_create(entries, batch_size=200)

        messages.success(
            request,
            f"Collecte SSH réussie pour « {server.name} » — "
            f"{len(entries)} log(s) importé(s), métriques mises à jour.",
        )
        return redirect("servers:list")

    # ── Helpers de parsing SSH ────────────────────────────────────────

    def _run(self, ssh, cmd: str, timeout: int = 5) -> str:
        """Exécute une commande SSH et retourne stdout."""
        try:
            _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
            return stdout.read().decode(errors="replace").strip()
        except Exception:
            return ""

    def _collect_metrics_ssh(self, ssh) -> dict:
        """Collecte CPU, RAM, Disk, Uptime via commandes SSH."""
        metrics = {}

        # ── CPU (top -bn1) ─────────────────────────────────────────
        top = self._run(ssh, "top -bn1 | grep 'Cpu(s)' | head -1")
        cpu_match = re.search(r"(\d+[\.,]\d+)\s*%?\s*id", top)
        if cpu_match:
            idle = float(cpu_match.group(1).replace(",", "."))
            metrics["cpu_percent"] = round(100.0 - idle, 1)

        # Fallback vmstat
        if "cpu_percent" not in metrics:
            vmstat = self._run(ssh, "vmstat 1 2 | tail -1")
            parts = vmstat.split()
            if len(parts) >= 15:
                try:
                    metrics["cpu_percent"] = round(100.0 - float(parts[14]), 1)
                except (ValueError, IndexError):
                    pass

        # ── RAM (free -m) ──────────────────────────────────────────
        free = self._run(ssh, "free -m | awk '/^Mem/{print $2,$3}'")
        parts = free.split()
        if len(parts) == 2:
            try:
                total, used = float(parts[0]), float(parts[1])
                if total > 0:
                    metrics["memory_percent"] = round(used / total * 100, 1)
            except ValueError:
                pass

        # ── Disk (df /) ────────────────────────────────────────────
        df = self._run(ssh, "df / | awk 'NR==2{print $5}' | tr -d '%'")
        try:
            metrics["disk_percent"] = float(df.strip())
        except ValueError:
            pass

        # ── Load average ────────────────────────────────────────────
        load = self._run(ssh, "cat /proc/loadavg")
        if load:
            try:
                metrics["load_average"] = float(load.split()[0])
            except (ValueError, IndexError):
                pass

        # ── Uptime (secondes) ──────────────────────────────────────
        uptime_raw = self._run(ssh, "cat /proc/uptime")
        if uptime_raw:
            try:
                metrics["uptime_seconds"] = int(float(uptime_raw.split()[0]))
            except (ValueError, IndexError):
                pass

        return metrics

    def _collect_logs_ssh(self, ssh, lines: int = 100) -> list[dict]:
        """Lit les derniers logs système via journalctl ou syslog."""
        logs = []

        # Essaie journalctl
        output = self._run(
            ssh,
            f"journalctl -n {lines} --no-pager -o short-iso 2>/dev/null",
            timeout=10,
        )
        if output:
            for line in output.splitlines():
                line = line.strip()
                if line:
                    logs.append({"level": _guess_level(line), "message": line})
            return logs

        # Fallback syslog
        for path in ["/var/log/syslog", "/var/log/messages"]:
            output = self._run(ssh, f"tail -n {lines} {path} 2>/dev/null", timeout=10)
            if output:
                for line in output.splitlines():
                    line = line.strip()
                    if line:
                        logs.append({"level": _guess_level(line), "message": line})
                return logs

        return logs


def _guess_level(line: str) -> str:
    """Devine le niveau de log depuis le contenu d'une ligne."""
    low = line.lower()
    if any(w in low for w in ["critical", "crit", "emerg", "alert", "fatal"]):
        return "CRITICAL"
    if any(w in low for w in [" error", "err:", "[err]", "failed", "failure"]):
        return "ERROR"
    if any(w in low for w in ["warn", "warning"]):
        return "WARNING"
    if "debug" in low:
        return "DEBUG"
    return "INFO"
