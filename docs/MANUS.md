# Manus-Limb

`limbs/manus_limb.py` fährt den gehosteten Agenten Manus über die API v2, nur mit `urllib`. Unterbau ist das Lauf-Modell in `limbs/agent_base.py`, das auch OpenManus und Cua nutzen sollen.

## Stand: gesperrt

Es gab bisher keinen echten Aufruf und keine verbrauchten Credits. Getestet ist nur gegen einen gefälschten Dienst.

| Sperre | Wo | Fällt, wenn |
|---|---|---|
| Nur Dienste auf diesem Rechner | `_base_url` in `limbs/manus_limb.py` | J4 gemergt, Key und Budget vom Menschen |
| Limb nicht startbar über den Orchestrator | `status: planned` in `limbs/registry.json` | dito |

## Vor dem ersten echten Lauf

1. J4 mergen. `manus.start` hat `risk: external`, die Prüfung des Tickets kommt von dort.
2. `_base_url` auf `https://api.manus.ai` beschränken, Test `test_echter_host_bleibt_gesperrt` anpassen, Status auf `active` setzen.
3. `MANUS_API_KEY`, `MANUS_BUDGET_RUN` und `MANUS_BUDGET_DAY` setzen. Nach J3 gehören sie in `env_allow`.
4. Einen Wächter einrichten, der `manus.status` regelmäßig aufruft. Ohne ihn greifen Timeout und Budget nicht.
5. Prüfen, ob die Tabelle unten noch stimmt.

## Belegtes aus der Doku

Gelesen am 2026-11-01 unter https://open.manus.ai/docs/v2/ und in `openapi_v2.json`.

| Punkt | Beleg |
|---|---|
| Status | `task.detail.task.status`: `running`, `stopped`, `waiting`, `error`, `deleted` |
| `stopped` ist nicht immer endgültig | `has_running_background_jobs` in `task.detail` |
| Credits je Task | `task.detail.task.credit_usage`, nur vorhanden, wenn Credits verbraucht wurden |
| Credits je Konto | `usage.list`: `credits` negativ bei Verbrauch, `type` ist `cost`, `refund` oder `grant` |
| Rückfragen | `status_detail.waiting_for_event_type`, bestätigt würde mit `task.confirmAction` |
| Grenzen je Minute | `task.create` 10, `task.detail` und `task.listMessages` 100, `task.stop` 40, `usage.list` 600 |
| Artefakte | `artifact.list` hat keinen Task-Filter, der Limb filtert nach `task_id` |

Unbelegt bleibt, was ein Credit kostet. Preise stehen nicht in der API-Doku.

Die Doku kennt kein Idempotenz-Feld für `task.create`. Deshalb wiederholt der Limb einen fehlgeschlagenen Start nicht.

## Grenzen

- `manus.collect` lädt keine Dateien, es speichert nur deren Metadaten. Die URLs kommen vom Dienst und sind Fremdinhalt.
- Rückfragen erscheinen als `confirmation`. Eine Karte in Apollo fehlt noch (Phase 3.4), der Lauf wartet bis zum Timeout.
- `task.sendMessage` ist nicht eingebaut. Laut Doku würde jede Nachricht eine ausstehende Bestätigung überspringen.

## Einstellungen

| Variable | Bedeutung |
|---|---|
| `MANUS_API_KEY` | Pflicht, nur aus der Umgebung |
| `MANUS_BUDGET_RUN` | Pflicht, Credits je Lauf |
| `MANUS_BUDGET_DAY` | Pflicht, Credits je Tag (UTC) |
| `MANUS_API_BASE` | Nur für Tests, muss derzeit auf diesen Rechner zeigen |
