"""Übersetzungen (Deutsch/Englisch) mit Live-Umschaltung.

Widgets registrieren sich per `on_change(callback)` und bauen ihre Texte in
`retranslate()` neu auf. Kein Qt-Import, damit das Modul überall nutzbar ist.
"""

from __future__ import annotations

from typing import Callable

LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English"}

_STRINGS: dict[str, dict[str, str]] = {
    # Kopf / Eingabe
    "app.subtitle": {"de": "Videos und Audio aus dem Web speichern",
                     "en": "Save video and audio from the web"},
    "input.placeholder": {"de": "Link einfügen oder hierher ziehen …",
                          "en": "Paste a link or drop it here …"},
    "btn.paste": {"de": "Einfügen", "en": "Paste"},
    "btn.analyze": {"de": "Analysieren", "en": "Analyze"},
    "btn.settings": {"de": "Einstellungen", "en": "Settings"},
    "btn.download": {"de": "Herunterladen", "en": "Download"},
    "status.analyzing": {"de": "Link wird analysiert …", "en": "Analyzing link …"},
    "status.no_link": {"de": "Kein gültiger Link gefunden.", "en": "No valid link found."},
    "status.clipboard_empty": {"de": "Die Zwischenablage enthält keinen Link.",
                               "en": "The clipboard does not contain a link."},
    "status.queued_many": {"de": "{n} Links zur Warteschlange hinzugefügt.",
                           "en": "Added {n} links to the queue."},
    "status.queued_one": {"de": "Zur Warteschlange hinzugefügt.", "en": "Added to the queue."},
    "banner.no_ffmpeg": {
        "de": "ffmpeg wurde nicht gefunden. Video und Ton können nicht zusammengeführt und "
              "Audio nicht umgewandelt werden – es werden Einzeldateien geladen.",
        "en": "ffmpeg was not found. Video and audio cannot be merged and audio cannot be "
              "converted – single files will be downloaded instead."},

    # Vorschau
    "preview.quality": {"de": "Qualität", "en": "Quality"},
    "preview.format": {"de": "Format", "en": "Format"},
    "quality.best": {"de": "Beste Qualität", "en": "Best quality"},
    "quality.audio": {"de": "Nur Audio", "en": "Audio only"},
    "preview.unknown_uploader": {"de": "Unbekannter Kanal", "en": "Unknown channel"},

    # Warteschlange
    "queue.title": {"de": "Warteschlange", "en": "Queue"},
    "queue.clear_done": {"de": "Fertige entfernen", "en": "Clear finished"},
    "queue.empty": {"de": "Noch keine Downloads.\nFüge oben einen Link ein, um zu starten.",
                    "en": "No downloads yet.\nPaste a link above to get started."},
    "footer.counts": {"de": "{active} aktiv, {waiting} wartend, {done} fertig",
                      "en": "{active} active, {waiting} waiting, {done} done"},
    "footer.legal": {
        "de": "Lade nur Inhalte herunter, an denen du die Rechte hast oder deren Nutzung erlaubt ist.",
        "en": "Only download content you own the rights to or are permitted to use."},

    # Job-Zustände
    "job.waiting": {"de": "Wartet …", "en": "Waiting …"},
    "job.starting": {"de": "Startet …", "en": "Starting …"},
    "job.downloading": {"de": "Lädt herunter", "en": "Downloading"},
    "job.processing": {"de": "Wird verarbeitet …", "en": "Processing …"},
    "job.done": {"de": "Fertig", "en": "Done"},
    "job.cancelled": {"de": "Abgebrochen", "en": "Cancelled"},
    "job.error": {"de": "Fehler", "en": "Error"},
    "job.eta": {"de": "noch {eta}", "en": "{eta} left"},
    "job.cancel": {"de": "Abbrechen", "en": "Cancel"},
    "job.retry": {"de": "Wiederholen", "en": "Retry"},
    "job.open": {"de": "Datei öffnen", "en": "Open file"},
    "job.folder": {"de": "Im Ordner zeigen", "en": "Show in folder"},
    "job.remove": {"de": "Entfernen", "en": "Remove"},
    "job.file_missing": {"de": "Die Datei wurde nicht gefunden.", "en": "The file could not be found."},

    # Fehler
    "error.login": {"de": "Für diesen Inhalt ist eine Anmeldung nötig (privat, altersbeschränkt "
                          "oder nur für Mitglieder). Tipp: In den Einstellungen Cookies aus dem "
                          "Browser verwenden.",
                    "en": "This content requires you to sign in (private, age-restricted or "
                          "members only). Tip: use browser cookies in the settings."},
    "error.unsupported": {"de": "Dieser Link wird nicht unterstützt.",
                          "en": "This link is not supported."},
    "error.unavailable": {"de": "Der Inhalt ist nicht (mehr) verfügbar oder in deinem Land gesperrt.",
                          "en": "The content is not available (anymore) or blocked in your country."},
    "error.network": {"de": "Netzwerkfehler – bitte Internetverbindung prüfen und erneut versuchen.",
                      "en": "Network error – please check your connection and try again."},
    "error.ffmpeg": {"de": "Die Verarbeitung mit ffmpeg ist fehlgeschlagen.",
                     "en": "Processing with ffmpeg failed."},
    "error.cancelled": {"de": "Der Vorgang wurde abgebrochen.", "en": "The operation was cancelled."},
    "error.unknown": {"de": "Unbekannter Fehler.", "en": "Unknown error."},
    "error.details": {"de": "Details: {detail}", "en": "Details: {detail}"},

    # Schließen
    "close.title": {"de": "Downloads laufen noch", "en": "Downloads in progress"},
    "close.text": {"de": "Es laufen noch {n} Download(s). Trotzdem beenden? Unfertige Downloads "
                         "werden abgebrochen und können später fortgesetzt werden.",
                   "en": "{n} download(s) are still running. Quit anyway? Unfinished downloads "
                         "will be cancelled and can be resumed later."},
    "close.quit": {"de": "Beenden", "en": "Quit"},
    "close.stay": {"de": "Weiter laden", "en": "Keep downloading"},

    # Einstellungen
    "settings.title": {"de": "Einstellungen", "en": "Settings"},
    "settings.general": {"de": "Allgemein", "en": "General"},
    "settings.language": {"de": "Sprache", "en": "Language"},
    "settings.folder": {"de": "Download-Ordner", "en": "Download folder"},
    "settings.browse": {"de": "Durchsuchen …", "en": "Browse …"},
    "settings.parallel": {"de": "Parallele Downloads", "en": "Parallel downloads"},
    "settings.cookies": {"de": "Cookies aus Browser", "en": "Cookies from browser"},
    "settings.cookies_none": {"de": "Keine", "en": "None"},
    "settings.cookies_hint": {
        "de": "Hilft bei Inhalten, die eine Anmeldung erfordern. Der Browser sollte dafür geschlossen sein.",
        "en": "Helps with content that requires signing in. The browser should be closed for this."},
    "settings.components": {"de": "Komponenten", "en": "Components"},
    "settings.ytdlp": {"de": "yt-dlp", "en": "yt-dlp"},
    "settings.check_update": {"de": "Nach Updates suchen", "en": "Check for updates"},
    "settings.update_now": {"de": "Jetzt aktualisieren", "en": "Update now"},
    "settings.checking": {"de": "Suche nach Updates …", "en": "Checking for updates …"},
    "settings.up_to_date": {"de": "Aktuell ({v}).", "en": "Up to date ({v})."},
    "settings.update_available": {"de": "Neue Version verfügbar: {v}", "en": "New version available: {v}"},
    "settings.update_frozen": {
        "de": "Neue Version {v} verfügbar. Bitte lade die neueste Kestrelgrab-Version herunter "
              "oder baue die App neu.",
        "en": "New version {v} available. Please download the latest Kestrelgrab release "
              "or rebuild the app."},
    "settings.update_failed": {"de": "Update-Prüfung fehlgeschlagen.", "en": "Update check failed."},
    "settings.updating": {"de": "Wird aktualisiert …", "en": "Updating …"},
    "settings.updated": {"de": "Aktualisiert. Bitte Kestrelgrab neu starten.",
                         "en": "Updated. Please restart Kestrelgrab."},
    "settings.update_error": {"de": "Aktualisierung fehlgeschlagen.", "en": "Update failed."},
    "settings.ffmpeg": {"de": "ffmpeg", "en": "ffmpeg"},
    "settings.js": {"de": "JS-Runtime (YouTube)", "en": "JS runtime (YouTube)"},
    "settings.found": {"de": "Gefunden: {path}", "en": "Found: {path}"},
    "settings.not_found": {"de": "Nicht gefunden", "en": "Not found"},
    "settings.js_missing_hint": {
        "de": "Ohne Deno oder Node funktionieren YouTube-Downloads eventuell nicht.",
        "en": "Without Deno or Node, YouTube downloads may not work."},
    "settings.save": {"de": "Speichern", "en": "Save"},
    "settings.cancel": {"de": "Abbrechen", "en": "Cancel"},
    "settings.choose_folder": {"de": "Download-Ordner wählen", "en": "Choose download folder"},
}

DEFAULT_LANGUAGE = "en"

_current = DEFAULT_LANGUAGE
_listeners: list[Callable[[], None]] = []


def current_language() -> str:
    return _current


def set_language(lang: str) -> None:
    global _current
    lang = lang if lang in LANGUAGES else "en"
    if lang == _current:
        return
    _current = lang
    for cb in list(_listeners):
        try:
            cb()
        except RuntimeError:
            # Widget bereits gelöscht → Listener entfernen
            remove_listener(cb)


def on_change(cb: Callable[[], None]) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def remove_listener(cb: Callable[[], None]) -> None:
    if cb in _listeners:
        _listeners.remove(cb)


def tr(key: str, **kwargs: object) -> str:
    entry = _STRINGS.get(key)
    text = entry.get(_current) or entry.get("en", key) if entry else key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def all_keys() -> list[str]:
    return list(_STRINGS)


def missing_translations() -> list[tuple[str, str]]:
    return [(k, lang) for k, v in _STRINGS.items() for lang in LANGUAGES if not v.get(lang)]
