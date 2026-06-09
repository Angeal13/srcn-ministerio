"""SRCN — Sync Scheduler: periodic fallback sync with provincial node."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger('srcn.scheduler')
_scheduler = None


def init_sync(app):
    global _scheduler
    if not app.config.get('SYNC_ENABLED'):
        return
    _scheduler = BackgroundScheduler()
    hour   = app.config.get('SYNC_HOUR', 2)
    minute = app.config.get('SYNC_MINUTE', 0)

    @_scheduler.scheduled_job(CronTrigger(hour=hour, minute=minute))
    def sync_job():
        with app.app_context():
            _full_sync(app)

    _scheduler.start()
    log.info(f"SRCN sync scheduler started — daily at {hour:02d}:{minute:02d}")


def _full_sync(app):
    """Push all pending RegistroSync records to provincial node."""
    from app.models.models import db, RegistroSync
    from app.utils.intranet_sync import _serializar_sujeto, _serializar_detencion, _serializar_warrant, _post_to_nodo
    from app.models.models import Sujeto, Detencion, Warrant
    import json

    pendientes = RegistroSync.query.filter_by(estado='pendiente').limit(200).all()
    if not pendientes:
        return

    registros = []
    for r in pendientes:
        try:
            if r.tipo_dato == 'sujeto':
                obj = Sujeto.query.filter_by(uuid=r.uuid_registro).first()
                if obj: registros.append({'tipo': 'sujeto', 'uuid': r.uuid_registro, 'datos': _serializar_sujeto(obj)})
            elif r.tipo_dato == 'detencion':
                obj = Detencion.query.filter_by(uuid=r.uuid_registro).first()
                if obj: registros.append({'tipo': 'detencion', 'uuid': r.uuid_registro, 'datos': _serializar_detencion(obj)})
            elif r.tipo_dato == 'warrant':
                obj = Warrant.query.filter_by(uuid=r.uuid_registro).first()
                if obj: registros.append({'tipo': 'warrant', 'uuid': r.uuid_registro, 'datos': _serializar_warrant(obj)})
            r.estado = 'enviado'
            r.intentos += 1
        except Exception as e:
            r.estado = 'error'
            r.error_mensaje = str(e)
            r.intentos += 1

    if registros:
        _post_to_nodo('/api/sync/push-sync', {'registros': registros})
    db.session.commit()
    log.info(f"Full sync complete: {len(registros)} registros enviados")
