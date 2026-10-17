"""Deterministic, batch-scoped alert suppression; no cross-request state."""
from collections import Counter
from datetime import datetime, timezone

SEVERITIES = {'info': 0, 'warning': 1, 'critical': 2}

def timestamp(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timestamps must include a timezone')
    return result.astimezone(timezone.utc)

def reduce_alert_noise(alerts, cooldown_minutes=15, minimum_severity='warning'):
    if not 0 <= cooldown_minutes <= 1440 or minimum_severity not in SEVERITIES:
        raise ValueError('Invalid suppression configuration')
    alerts = list(alerts)
    if len(alerts) > 1000:
        raise ValueError('At most 1000 alerts are accepted')
    seen_ids = set()
    normalized = []
    for alert in alerts:
        if alert['alert_id'] in seen_ids:
            raise ValueError('alert_id must be unique within a batch')
        seen_ids.add(alert['alert_id'])
        if alert['severity'] not in SEVERITIES:
            raise ValueError('Unknown severity')
        signature = (alert['environment'].strip().casefold(), alert['service'].strip().casefold(),
                     alert['alert_name'].strip().casefold(), alert['severity'])
        normalized.append((timestamp(alert['timestamp']), signature, alert))
    actionable, suppressed, last_kept = [], [], {}
    for observed_at, signature, alert in sorted(normalized, key=lambda item: (item[0], item[2]['alert_id'])):
        decision = {**alert, 'signature': list(signature)}
        previous = last_kept.get(signature)
        if SEVERITIES[alert['severity']] < SEVERITIES[minimum_severity]:
            reason = 'below_minimum_severity'
        elif previous is not None and (observed_at - previous).total_seconds() < cooldown_minutes * 60:
            reason = 'duplicate_within_cooldown'
        else:
            last_kept[signature] = observed_at
            actionable.append(decision)
            continue
        suppressed.append({**decision, 'suppression_reason': reason})
    return {'actionable_alerts': actionable, 'suppressed_alerts': suppressed,
            'summary': {'received': len(alerts), 'actionable': len(actionable), 'suppressed': len(suppressed),
                        'reduction_percent': round(100 * len(suppressed) / max(len(alerts), 1), 2),
                        'reasons': dict(Counter(a['suppression_reason'] for a in suppressed))}}
