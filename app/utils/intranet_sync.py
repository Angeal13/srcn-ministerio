"""
SRCN — Sincronización Intranet en Tiempo Real
Push de sujetos, detenciones, warrants y alertas al nodo provincial.
Patrón idéntico a Bioko Health intranet_sync.py.
"""
import logging
import requests
import json
from datetime import datetime
from threading import Thread, Lock
from collections import deque

log = logging.getLogger('srcn.intranet')
_queue = deque(maxlen=5000)
_lock  = Lock()
_app   = None


def init_intranet(app):
    global _app
    if not app.config.get('INTRANET_MODE'):
        return
    _app = app
    log.info("SRCN Intranet Sync initialized")


def encolar_registro(tipo, uuid):
    """Encola un registro para sync inmediato con el nodo provincial."""
    with _lock:
        _queue.append({'tipo': tipo, 'uuid': uuid, 'timestamp': datetime.utcnow().isoformat()})
    t = Thread(target=_flush_queue, daemon=True)
    t.start()


def propagar_alerta_profugo(alerta_uuid):
    """Push inmediato de alerta de prófugo al nodo provincial para difusión nacional."""
    if not _app:
        return
    with _app.app_context():
        from app.models.models import AlertaProfugo
        alerta = AlertaProfugo.query.filter_by(uuid=alerta_uuid).first()
        if not alerta:
            return
        payload = {
            'uuid': alerta.uuid,
            'warrant_uuid': alerta.warrant_uuid,
            'sujeto_uuid': alerta.sujeto_uuid,
            'sujeto_dni': alerta.sujeto_dni,
            'sujeto_nombres': alerta.sujeto_nombres,
            'sujeto_apellidos': alerta.sujeto_apellidos,
            'huella_hash': alerta.huella_hash,
            'nivel_urgencia': alerta.nivel_urgencia,
            'provincia_origen': alerta.provincia_origen,
            'descripcion_breve': alerta.descripcion_breve,
            'activa': alerta.activa,
        }
        _post_to_nodo('/api/sync/recibir-alerta-profugo', payload)


def _flush_queue():
    if not _app:
        return
    with _app.app_context():
        batch = []
        with _lock:
            while _queue and len(batch) < 50:
                batch.append(_queue.popleft())
        if not batch:
            return
        registros = []
        from app.models.models import Sujeto, Detencion, Warrant
        for item in batch:
            tipo = item['tipo']
            uuid = item['uuid']
            datos = None
            if tipo == 'sujeto':
                obj = Sujeto.query.filter_by(uuid=uuid).first()
                if obj:
                    datos = _serializar_sujeto(obj)
            elif tipo == 'detencion':
                obj = Detencion.query.filter_by(uuid=uuid).first()
                if obj:
                    datos = _serializar_detencion(obj)
            elif tipo == 'warrant':
                obj = Warrant.query.filter_by(uuid=uuid).first()
                if obj:
                    datos = _serializar_warrant(obj)
            if datos:
                registros.append({'tipo': tipo, 'uuid': uuid, 'datos': datos})
        if registros:
            _post_to_nodo('/api/sync/push-sync', {'registros': registros})


def _post_to_nodo(path, payload):
    nodo_url = _app.config.get('PROVINCIAL_NODE_URL', '')
    token    = _app.config.get('SYNC_API_TOKEN', '')
    if not nodo_url:
        return
    try:
        r = requests.post(
            nodo_url.rstrip('/') + path,
            json=payload,
            headers={'X-SRCN-Token': token, 'Content-Type': 'application/json'},
            timeout=8,
            verify=False  # mTLS handled at nginx layer
        )
        if not r.ok:
            log.warning(f"Sync POST {path} → {r.status_code}: {r.text[:200]}")
    except requests.exceptions.RequestException as e:
        log.error(f"Sync POST {path} failed: {e}")


def _serializar_sujeto(s):
    return {
        'uuid': s.uuid,
        'numero_expediente': s.numero_expediente,
        'dni': s.dni,
        'nombres': s.nombres,
        'apellidos': s.apellidos,
        'fecha_nacimiento': s.fecha_nacimiento.isoformat() if s.fecha_nacimiento else None,
        'sexo': s.sexo,
        'nacionalidad': s.nacionalidad,
        'huella_hash': s.huella_hash,
        'nivel_riesgo': s.nivel_riesgo,
        'es_buscado': s.es_buscado,
        'provincia_warrant': s.provincia_warrant,
        'direccion': s.direccion,
        'telefono': s.telefono,
    }


def _serializar_detencion(d):
    return {
        'uuid': d.uuid,
        'sujeto_uuid': d.sujeto.uuid,
        'comisaria_codigo': d.comisaria.codigo if d.comisaria else None,
        'fecha_detencion': d.fecha_detencion.isoformat(),
        'lugar_detencion': d.lugar_detencion,
        'motivo': d.motivo,
        'descripcion': d.descripcion,
        'estado': d.estado,
    }


def _serializar_warrant(w):
    return {
        'uuid': w.uuid,
        'sujeto_uuid': w.sujeto.uuid,
        'provincia_emisora': w.provincia_emisora,
        'numero_judicial': w.numero_judicial,
        'juez_emisor': w.juez_emisor,
        'descripcion': w.descripcion,
        'nivel_urgencia': w.nivel_urgencia,
        'estado': w.estado,
        'fecha_emision': w.fecha_emision.isoformat() if w.fecha_emision else None,
        'fecha_expiracion': w.fecha_expiracion.isoformat() if w.fecha_expiracion else None,
        'delitos_asociados': json.loads(w.delitos_asociados) if w.delitos_asociados else [],
    }
