#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║            LogMonitor Agent  —  v1.0                            ║
║  Script à exécuter sur les serveurs distants à surveiller.      ║
║  Collecte les métriques système et les logs, puis les envoie    ║
║  vers LogMonitor via l'API REST.                                ║
╚══════════════════════════════════════════════════════════════════╝

PRÉREQUIS (sur le serveur distant) :
    pip install psutil

UTILISATION :
    # Envoi unique
    python logmonitor_agent.py --url http://LOGMONITOR_IP:8000 --source "nom-serveur"

    # Mode démon (boucle toutes les 60 s)
    python logmonitor_agent.py --url http://LOGMONITOR_IP:8000 --source "nom-serveur" --loop

    # Avec clé API
    python logmonitor_agent.py --url http://... --source "nom-serveur" --key "MA_CLE_API"

    # Personnaliser l'intervalle et le nombre de logs
    python logmonitor_agent.py --url http://... --source "nom-serveur" --loop --interval 30 --lines 200

ENDPOINTS UTILISÉS :
    POST /api/v1/servers/metrics/    ← mise à jour CPU/RAM/Disk du serveur
    POST /api/v1/logs/ingest/bulk/   ← envoi des logs système
"""

import argparse
import json
import logging
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone as tz

# ── Logging local de l'agent ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("logmonitor.agent")

# ── psutil (métriques système) ────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    log.warning("psutil non installé — les métriques CPU/RAM/Disk ne seront pas collectées.")
    log.warning("Installez-le avec : pip install psutil")


# ══════════════════════════════════════════════════════════════════════
# Collecte des métriques système
# ══════════════════════════════════════════════════════════════════════

def collect_metrics() -> dict:
    """Collecte CPU, RAM, Disk, Load, Uptime via psutil."""
    if not HAS_PSUTIL:
        return {}

    metrics = {
        "cpu_percent":    psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent":   psutil.disk_usage("/").percent,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
    }

    # load_average uniquement sur Unix
    if hasattr(psutil, "getloadavg"):
        try:
            metrics["load_average"] = round(psutil.getloadavg()[0], 2)
        except OSError:
            pass

    return metrics


# ══════════════════════════════════════════════════════════════════════
# Collecte des logs système
# ══════════════════════════════════════════════════════════════════════

def collect_logs_linux(lines: int = 100) -> list[dict]:
    """Lit les logs système via journalctl ou /var/log/syslog."""
    import subprocess

    # 1. Essaie journald
    try:
        result = subprocess.run(
            ["journalctl", "-n", str(lines), "--no-pager", "-o", "short-iso",
             "--output-fields=PRIORITY,MESSAGE,_SYSTEMD_UNIT"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0 and result.stdout.strip():
            entries = []
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                level = _guess_level_from_line(line)
                entries.append({"level": level, "message": line, "logger": "journald"})
            return entries
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Fallback : fichiers syslog
    for logfile in ["/var/log/syslog", "/var/log/messages", "/var/log/auth.log"]:
        if not os.path.exists(logfile):
            continue
        try:
            with open(logfile, "r", errors="replace") as f:
                recent = f.readlines()[-lines:]
            entries = []
            for line in recent:
                line = line.strip()
                if line:
                    entries.append({
                        "level": _guess_level_from_line(line),
                        "message": line,
                        "logger": f"syslog:{os.path.basename(logfile)}",
                    })
            return entries
        except PermissionError:
            log.warning(f"Permission refusée pour lire {logfile} — essayez avec sudo")

    log.warning("Aucune source de logs accessible (journald, syslog). Essayez avec sudo.")
    return []


def collect_logs_windows(lines: int = 100) -> list[dict]:
    """Lit le journal système Windows via wevtutil."""
    import subprocess

    try:
        result = subprocess.run(
            ["wevtutil", "qe", "System", f"/c:{lines}", "/rd:true", "/f:text"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        entries = []
        current_msg_parts = []
        current_level = "INFO"

        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Event["):
                if current_msg_parts:
                    entries.append({
                        "level": current_level,
                        "message": " | ".join(current_msg_parts[:5]),
                        "logger": "windows-event",
                    })
                current_msg_parts = []
                current_level = "INFO"
            elif stripped.lower().startswith("level:"):
                lvl = stripped.split(":", 1)[1].strip().upper()
                if "ERROR" in lvl or "CRITICAL" in lvl:
                    current_level = "ERROR"
                elif "WARNING" in lvl or "WARN" in lvl:
                    current_level = "WARNING"
            elif stripped:
                current_msg_parts.append(stripped)

        return entries[-lines:]

    except FileNotFoundError:
        log.warning("wevtutil introuvable — collecte Windows Event Log impossible.")
    except Exception as exc:
        log.warning(f"Erreur collecte Windows Event Log : {exc}")

    return []


def _guess_level_from_line(line: str) -> str:
    """Devine le niveau de log depuis le contenu de la ligne."""
    low = line.lower()
    if any(w in low for w in ["critical", "crit", "emerg", "alert", "fatal"]):
        return "CRITICAL"
    if any(w in low for w in [" error", "err:", "[err]", "failed", "failure", "refused"]):
        return "ERROR"
    if any(w in low for w in ["warn", "[warn]", "warning"]):
        return "WARNING"
    if any(w in low for w in ["debug", "[debug]"]):
        return "DEBUG"
    return "INFO"


def collect_logs(lines: int = 100) -> list[dict]:
    """Collecte les logs selon la plateforme."""
    system = platform.system()
    if system == "Windows":
        return collect_logs_windows(lines)
    return collect_logs_linux(lines)


# ══════════════════════════════════════════════════════════════════════
# Envoi vers l'API LogMonitor
# ══════════════════════════════════════════════════════════════════════

def _api_post(url: str, payload: dict, api_key: str = "") -> dict | None:
    """Effectue un POST JSON vers l'API LogMonitor."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent":   f"LogMonitor-Agent/1.0 Python/{platform.python_version()}",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        log.error(f"HTTP {exc.code} — {exc.url}\n  {body[:300]}")
    except urllib.error.URLError as exc:
        log.error(f"Impossible de joindre LogMonitor : {exc.reason}")
        log.error("Vérifiez que le serveur LogMonitor est démarré et l'URL correcte.")
    except Exception as exc:
        log.error(f"Erreur inattendue : {exc}")
    return None


def push_metrics(base_url: str, server_name: str, metrics: dict, api_key: str = "") -> bool:
    """Envoie les métriques système au serveur LogMonitor."""
    if not metrics:
        return False

    payload = {"server_name": server_name, **metrics}
    url = f"{base_url.rstrip('/')}/api/v1/servers/metrics/"
    result = _api_post(url, payload, api_key)

    if result:
        log.info(
            f"Métriques envoyées ✓  CPU={metrics.get('cpu_percent', '?')}%  "
            f"RAM={metrics.get('memory_percent', '?')}%  "
            f"Disk={metrics.get('disk_percent', '?')}%"
        )
        return True
    return False


def push_logs(base_url: str, server_name: str, logs: list[dict], api_key: str = "") -> bool:
    """Envoie les logs système au serveur LogMonitor (bulk)."""
    if not logs:
        log.info("Aucun log à envoyer.")
        return True

    entries = [
        {
            "level":   entry.get("level", "INFO"),
            "message": entry.get("message", "")[:2000],
            "source":  server_name,
            "logger":  entry.get("logger", "logmonitor.agent"),
        }
        for entry in logs
        if entry.get("message", "").strip()
    ]

    if not entries:
        return True

    payload = {"logs": entries}
    url = f"{base_url.rstrip('/')}/api/v1/logs/ingest/bulk/"
    result = _api_post(url, payload, api_key)

    if result:
        log.info(f"Logs envoyés ✓  {result.get('ingested', 0)}/{len(entries)} ingérés")
        if result.get("errors"):
            log.warning(f"  {len(result['errors'])} erreur(s) d'ingestion")
        return True
    return False


# ══════════════════════════════════════════════════════════════════════
# Logique principale
# ══════════════════════════════════════════════════════════════════════

def run_once(args: argparse.Namespace):
    """Effectue une collecte complète et l'envoie à LogMonitor."""
    hostname = socket.gethostname()
    log.info(f"Collecte depuis {hostname} → LogMonitor : {args.url}")

    # ── Métriques ─────────────────────────────────────────────────────
    metrics = collect_metrics()
    if metrics:
        push_metrics(args.url, args.source, metrics, args.key)
    else:
        log.warning("Aucune métrique collectée (psutil absent ?).")

    # ── Logs ──────────────────────────────────────────────────────────
    log.info(f"Collecte des {args.lines} dernières lignes de logs système…")
    logs = collect_logs(args.lines)
    log.info(f"{len(logs)} log(s) collecté(s).")
    push_logs(args.url, args.source, logs, args.key)


def main():
    parser = argparse.ArgumentParser(
        description="LogMonitor Agent — Collecte et envoi de métriques et logs système.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python logmonitor_agent.py --url http://192.168.1.100:8000 --source "web-prod-01"
  python logmonitor_agent.py --url http://mon-logmonitor.com --source "db-01" --loop --interval 30
  python logmonitor_agent.py --url http://... --source "api-gateway" --key "secret123" --lines 200
        """
    )
    parser.add_argument("--url",      required=True,         help="URL de base de LogMonitor (ex: http://192.168.1.10:8000)")
    parser.add_argument("--source",   required=True,         help="Nom exact du serveur dans LogMonitor")
    parser.add_argument("--key",      default="",            help="Clé API X-API-Key (optionnel si DEBUG=True)")
    parser.add_argument("--lines",    type=int, default=100, help="Nombre de lignes de logs à envoyer par cycle (défaut: 100)")
    parser.add_argument("--loop",     action="store_true",   help="Mode démon : collecte en boucle")
    parser.add_argument("--interval", type=int, default=60,  help="Intervalle en secondes entre chaque collecte (défaut: 60)")
    args = parser.parse_args()

    if args.loop:
        log.info(f"Mode démon démarré — collecte toutes les {args.interval}s. Ctrl+C pour arrêter.")
        try:
            while True:
                try:
                    run_once(args)
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    log.error(f"Erreur lors de la collecte : {exc}")
                log.info(f"Prochain cycle dans {args.interval}s…")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Agent arrêté.")
    else:
        run_once(args)


if __name__ == "__main__":
    main()
