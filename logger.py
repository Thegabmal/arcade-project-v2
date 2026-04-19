import os
import sys
import json
import datetime
import threading
from typing import Optional

# ─────────────────────────────────────────────
# QUEUE SSE — thread-local pour le streaming Flask
# ─────────────────────────────────────────────
_thread_local = threading.local()


def set_thread_event_queue(q):
    """Associe une queue d'événements SSE au thread courant."""
    _thread_local.event_queue = q


def clear_thread_event_queue():
    """Désassocie la queue du thread courant."""
    _thread_local.event_queue = None


def get_thread_event_queue():
    """Retourne la queue SSE du thread courant (pour propagation aux sous-threads)."""
    return getattr(_thread_local, "event_queue", None)


def _push_event(event_type: str, data: dict):
    """Envoie un événement dans la queue SSE du thread courant (si définie)."""
    q = getattr(_thread_local, "event_queue", None)
    if q is not None:
        try:
            q.put_nowait({"type": event_type, "data": data})
        except Exception:
            pass

# Forcer UTF-8 sur Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

LOG_FILE = "session_log.txt"


def push_event(event_type: str, data: dict):
    """Pousse un événement SSE depuis n'importe quel contexte (accès direct)."""
    _push_event(event_type, data)


# ─────────────────────────────────────────────
# PREVIEW CODE — stockage global par session_id
# Accessible depuis n'importe quel thread (route Flask incluse)
# ─────────────────────────────────────────────

_preview_store: dict[str, str] = {}      # session_id → html
_preview_store_lock = threading.Lock()


def set_preview_session_id(session_id: str):
    """Associe le thread courant à une session_id pour le stockage preview."""
    _thread_local.preview_session_id = session_id


def store_code_preview(html: str):
    """Stocke le code HTML généré en Phase 3 pour le live preview."""
    _thread_local.preview_code = html  # backward compat
    sid = getattr(_thread_local, "preview_session_id", None)
    if sid:
        with _preview_store_lock:
            _preview_store[sid] = html


def get_code_preview() -> str | None:
    """Retourne le code HTML prévisualisable du thread courant (backward compat)."""
    return getattr(_thread_local, "preview_code", None)


def get_preview_by_session(session_id: str) -> str | None:
    """Retourne le preview d'une session depuis n'importe quel thread."""
    with _preview_store_lock:
        return _preview_store.get(session_id)


def clear_code_preview():
    """Efface le code de preview du thread courant et du store global."""
    _thread_local.preview_code = None
    sid = getattr(_thread_local, "preview_session_id", None)
    if sid:
        with _preview_store_lock:
            _preview_store.pop(sid, None)
        _thread_local.preview_session_id = None

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "magenta": "\033[95m",
    "blue": "\033[94m",
    "white": "\033[97m",
    "grey": "\033[90m",
}

PHASE_COLORS = {
    "PHASE1": "cyan",
    "PHASE2": "blue",
    "PHASE3": "magenta",
    "PHASE4": "yellow",
    "PHASE5": "green",
    "SUPPORT": "grey",
    "COORDINATEUR": "white",
    "SUCCESS": "green",
    "ERROR": "red",
    "WARNING": "yellow",
    "INFO": "white",
}


def _color(text: str, color: str) -> str:
    c = COLORS.get(color, "")
    reset = COLORS["reset"]
    return f"{c}{text}{reset}"


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _write_log(level: str, phase: str, message: str):
    ts = _timestamp()
    line = f"[{ts}] [{level}] [{phase}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    # Accumulate in thread-local buffer for per-game log saving
    buf = getattr(_thread_local, "log_buffer", None)
    if buf is not None:
        buf.append(line)


def get_session_log() -> str:
    """Retourne le log accumulé pour la session courante."""
    buf = getattr(_thread_local, "log_buffer", None)
    if buf is not None:
        return "".join(buf)
    # Fallback : lire le fichier
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


class Logger:
    def __init__(self, phase: str = "INFO"):
        self.phase = phase

    def _log(self, level: str, message: str, color: str = "white"):
        ts = _timestamp()
        phase_str = _color(f"[{self.phase}]", PHASE_COLORS.get(self.phase, "white"))
        level_str = _color(f"[{level}]", color)
        ts_str = _color(f"[{ts}]", "grey")
        print(f"{ts_str} {phase_str} {level_str} {message}")
        _write_log(level, self.phase, message)

    def info(self, message: str):
        self._log("INFO", message, "white")
        _push_event("info", {"message": message, "phase": self.phase})

    def success(self, message: str):
        self._log("SUCCESS", _color(message, "green"), "green")
        _push_event("success", {"message": message, "phase": self.phase})

    def warning(self, message: str):
        self._log("WARNING", _color(message, "yellow"), "yellow")
        _push_event("warning", {"message": message, "phase": self.phase})

    def error(self, message: str):
        self._log("ERROR", _color(message, "red"), "red")
        _push_event("error", {"message": message, "phase": self.phase})

    def score(self, label: str, value: float, max_value: float = 10.0):
        pct = value / max_value
        if pct >= 0.8:
            color = "green"
        elif pct >= 0.6:
            color = "yellow"
        else:
            color = "red"
        score_str = _color(f"{value:.1f}/{max_value:.1f}", color)
        self._log("SCORE", f"{label}: {score_str}", color)
        _push_event("score", {"label": label, "value": value, "max": max_value, "phase": self.phase})

    def section(self, title: str):
        sep = "-" * 60
        print(f"\n{_color(sep, 'cyan')}")
        print(_color(f"  {title}", "bold"))
        print(f"{_color(sep, 'cyan')}")
        _write_log("SECTION", self.phase, title)
        _push_event("phase_start", {"title": title, "phase": self.phase})

    def agent_start(self, agent_name: str, description: str = ""):
        msg = f"> {agent_name}"
        if description:
            msg += f" -- {description}"
        self._log("AGENT", msg, "cyan")
        _push_event("agent_start", {"agent": agent_name, "phase": self.phase, "description": description})

    def agent_done(self, agent_name: str, result_summary: str = ""):
        msg = f"OK {agent_name}"
        if result_summary:
            msg += f" -- {result_summary}"
        self._log("DONE", msg, "green")
        _push_event("agent_done", {"agent": agent_name, "phase": self.phase, "result": result_summary})


# Loggers par phase
coordinateur_log = Logger("COORDINATEUR")
phase1_log = Logger("PHASE1")
phase2_log = Logger("PHASE2")
phase3_log = Logger("PHASE3")
phase4_log = Logger("PHASE4")
phase5_log = Logger("PHASE5")
support_log = Logger("SUPPORT")


def init_session():
    """Initialise le fichier de log pour la session.
    Append au fichier existant (ne pas écraser les runs précédents).
    """
    _thread_local.log_buffer = []
    header = (
        f"\n{'='*70}\n"
        f"SESSION DÉMARRÉE : {datetime.datetime.now().isoformat()}\n"
        f"{'='*70}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:  # "a" = append, pas "w"
        f.write(header)
    _thread_local.log_buffer.append(header)
