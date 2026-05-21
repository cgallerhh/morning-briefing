# Morning Briefing

Automatisiertes deutschsprachiges Morning Briefing mit Fokus auf Welt-News, KI/AI und EU/Deutschland-Regulierung. Die Pipeline sammelt Meldungen aus einer festen Quellenliste, entfernt Dubletten und erzeugt per OpenAI API ein kompaktes Markdown-Briefing.

## Struktur

- `config/sources.yml` - feste Kern- und Ergaenzungsquellen
- `prompts/morning_briefing_prompt.md` - Redaktionsprompt und Ausgabeformat
- `src/collect_sources.py` - sammelt RSS-Feeds und Webseiten, protokolliert Ausfaelle, entfernt Dubletten
- `src/generate_briefing.py` - erzeugt das deutsche Briefing via OpenAI
- `src/send_email.py` - Gmail-kompatibler SMTP-Versand als formatierte HTML-Mail
- `outputs/` - erzeugte Briefings als Markdown
- `.github/workflows/morning-briefing.yml` - werktaeglicher GitHub-Actions-Lauf plus manuelle Ausfuehrung

## Quellen

Kernquellen:

1. The Economist Espresso
2. The Intelligence - The Economist
3. Axios Today
4. Straight Arrow News - Unbiased Updates
5. The Decoder
6. The Rundown AI
7. The Batch von DeepLearning.AI

Ergaenzungsquellen:

1. MIT Technology Review - The Algorithm
2. Stanford HAI
3. Heise online
4. Euractiv

Die konkrete Konfiguration liegt in `config/sources.yml`. Wenn einzelne Quellen keine stabilen RSS-Feeds anbieten oder Paywalls/App-Zugriff nutzen, versucht die Sammlung eine Webseiten-Auswertung und fuehrt Ausfaelle sichtbar im Zwischenergebnis auf.

## Lokale Ausfuehrung

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."
python -m src.collect_sources
python -m src.generate_briefing
```

Das Ergebnis wird als `outputs/morning-briefing-YYYY-MM-DD.md` gespeichert. Der Sammelschritt schreibt zusaetzlich `outputs/collected-sources.json`, damit nachvollziehbar bleibt, welche Quellen und Fehler in den Lauf eingegangen sind.

## GitHub Actions

Der Workflow ist manuell per `workflow_dispatch` startbar und laeuft werktags per Cron:

```yaml
0 5 * * 1-5
```

GitHub-Cron laeuft in UTC. `05:00 UTC` ist eine Sommerzeit-Naeherung fuer `07:00 Europe/Berlin`. In der Winterzeit muss der Cron-Ausdruck auf `06:00 UTC` angepasst werden, sofern keine separate Timezone-Unterstuetzung genutzt wird.

### Workflow manuell starten

1. Repository auf GitHub oeffnen.
2. Den Tab `Actions` waehlen.
3. Links den Workflow `Morning Briefing` anklicken.
4. Rechts `Run workflow` auswaehlen.
5. Den gewuenschten Branch auswaehlen, zum Beispiel `main` nach dem Merge.
6. Noch einmal `Run workflow` bestaetigen.
7. Nach Abschluss des Laufs den Run oeffnen und unter `Artifacts` die Datei `morning-briefing-...` herunterladen.

Der Workflow erzeugt `outputs/morning-briefing-YYYY-MM-DD.md` und laedt diese Markdown-Datei zusammen mit `outputs/collected-sources.json` als GitHub Actions Artifact hoch. Die Datei wird in dieser Minimalversion nicht automatisch committed.

## GitHub Secrets und Variablen

Erforderliches Secret:

- `OPENAI_API_KEY` - API-Key fuer die Briefing-Erstellung

Der Workflow akzeptiert zusaetzlich den vorhandenen Secret-Namen `openAiAPI` als Fallback. Empfohlen ist langfristig trotzdem `OPENAI_API_KEY`, weil dieser Name in Tools und Dokumentationen ueblich ist.

Optionale Repository Variable:

- `OPENAI_MODEL` - OpenAI-Modell, Standard im Workflow: `gpt-4o-mini`

Wenn `OPENAI_MODEL` versehentlich als Secret statt als Variable angelegt wurde, nutzt der Workflow diesen Wert ebenfalls.

Zusaetzlich benoetigtes Secret fuer Gmail-Mailversand:

- `GMAIL_APP_PASSWORD` - Gmail-App-Passwort fuer `christian.galler@gmail.com`

Optionale SMTP-Secrets fuer spaetere Anpassungen:

- `SMTP_PASSWORD` - Alternative zu `GMAIL_APP_PASSWORD`
- `SMTP_SUBJECT` - eigener Betreff, falls der Standard `Morning Briefing` nicht gewuenscht ist

Der Workflow nutzt aktuell fest `christian.galler@gmail.com` als Absender und Empfaenger. Wetterdaten sind nicht aktiviert.

Es werden keine Secrets ins Repository geschrieben. Fehlende Pflichtwerte fuehren zu einem sichtbaren Fehler. Nicht erreichbare Einzelquellen brechen den Sammellauf nicht ab; sie werden in `outputs/collected-sources.json` unter `source_errors` protokolliert.

## Mailversand ueber Gmail

Der Workflow sendet das Briefing zusaetzlich als formatierte HTML-Mail ueber den Gmail-Account `christian.galler@gmail.com` an `christian.galler@gmail.com`. Dafuer wird ein Gmail-App-Passwort als GitHub Secret benoetigt.

Zusaetzlich benoetigtes Secret:

- `GMAIL_APP_PASSWORD` - Gmail-App-Passwort fuer `christian.galler@gmail.com`

Lokaler Test:

```bash
export GMAIL_APP_PASSWORD="..."
python -m src.send_email outputs/morning-briefing-YYYY-MM-DD.md
```

## Tests

```bash
pip install -r requirements.txt pytest
pytest
```
