"""
SRCN — Servidor Central / Ministerio del Interior
==================================================
Activo cuando STATION_MODE = 'central_server'

Responsabilidades:
  1. Índice nacional de sujetos y warrants (todos los UUIDs + provincia de origen)
  2. Resolver verificaciones inter-provinciales: localiza el nodo correcto y lo consulta
  3. Propagar alertas de prófugos a TODAS las provincias simultáneamente
  4. Exportar estadísticas a Fiscalía y organismos judiciales
  5. Dashboard nacional para el Ministerio del Interior

Flujo verificación inter-provincial:
  Comisaría Bata (Litoral)
    → POST /api/nacional/verificar {dni: X}
    → Central busca en índice: "X pertenece a Bioko Norte"
    → Central GET /provincial/expediente/{uuid} → Nodo Bioko Norte
    → Nodo Bioko Norte devuelve expediente completo
    → Central retorna a Litoral con el expediente
    → Tiempo total: < 8 segundos
"""
import json
import logging
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

from flask import Blueprint, render_template, jsonify, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app.models.models import (db, Sujeto, Detencion, Warrant, AlertaProfugo,
                                Provincia, RegistroSync, NodoComisaria,
                                CacheExpediente, TransferenciaDetenido)

log = logging.getLogger('srcn.central')
provincial_bp = Blueprint('provincial', __name__)

# ── Province → Node URL map (loaded from DB) ──────────────────
def _get_nodo_url(provincia_codigo):
    prov = Provincia.query.filter_by(codigo=provincia_codigo).first()
    return prov.nodo_url if prov else None


def requiere_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-SRCN-Token', '')
        expected = current_app.config.get('SYNC_API_TOKEN', '')
        if not token or token != expected:
            return jsonify({'error': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated


def solo_central(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        mode = current_app.config.get('STATION_MODE', '')
        if not current_user.is_authenticated:
            abort(401)
        if mode != 'central_server':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── DASHBOARD NACIONAL ────────────────────────────────────────
@provincial_bp.route('/dashboard')
@login_required
@solo_central
def dashboard():
    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    total_sujetos       = Sujeto.query.filter_by(activo=True).count()
    warrants_activos    = Warrant.query.filter_by(estado='activo').count()
    warrants_ejecutados = Warrant.query.filter(
        Warrant.estado == 'ejecutado',
        Warrant.fecha_ejecucion >= fecha_inicio).count()
    alertas_activas     = AlertaProfugo.query.filter_by(activa=True).count()
    detenciones_mes     = Detencion.query.filter(
        Detencion.fecha_detencion >= fecha_inicio).count()

    provincias      = Provincia.query.filter_by(activa=True).all()
    alertas_criticas = AlertaProfugo.query.filter_by(
        activa=True, nivel_urgencia='critico').order_by(
        AlertaProfugo.creada_en.desc()).limit(5).all()

    top_warrants = Warrant.query.filter_by(estado='activo').order_by(
        Warrant.fecha_emision.desc()).limit(10).all()

    return render_template('provincial/dashboard.html',
                           total_sujetos=total_sujetos,
                           warrants_activos=warrants_activos,
                           warrants_ejecutados=warrants_ejecutados,
                           alertas_activas=alertas_activas,
                           detenciones_mes=detenciones_mes,
                           provincias=provincias,
                           alertas_criticas=alertas_criticas,
                           top_warrants=top_warrants,
                           dias=dias,
                           es_central=True)


# ── VERIFICACIÓN NACIONAL ─────────────────────────────────────
@provincial_bp.route('/verificar', methods=['POST'])
@requiere_token
def verificar_nacional():
    """
    Endpoint principal de resolución inter-provincial.
    Llamado por nodos provinciales cuando el sujeto no está en su índice local.
    """
    data = request.get_json()
    dni  = data.get('dni', '').strip()
    uuid = data.get('uuid', '').strip()

    # 1. Check national index first
    sujeto = None
    if dni:
        sujeto = Sujeto.query.filter_by(dni=dni).first()
    if not sujeto and uuid:
        sujeto = Sujeto.query.filter_by(uuid=uuid).first()

    if not sujeto:
        return jsonify({'encontrado': False, 'warrant_activo': False})

    # 2. Check for active warrant in national index
    warrant = Warrant.query.filter_by(sujeto_id=sujeto.id, estado='activo').first()

    if not warrant:
        return jsonify({
            'encontrado': True,
            'warrant_activo': False,
            'sujeto_nombre': sujeto.nombre_completo,
            'expediente': sujeto.numero_expediente,
            'nivel_riesgo': sujeto.nivel_riesgo,
            'provincia_origen': sujeto.provincia_warrant,
        })

    # 3. Warrant found — fetch full record from issuing province
    provincia_emisora = warrant.provincia_emisora
    nodo_url = _get_nodo_url(provincia_emisora)
    expediente_completo = None

    if nodo_url:
        try:
            token = current_app.config.get('SYNC_API_TOKEN', '')
            r = requests.get(
                nodo_url.rstrip('/') + f'/provincial/expediente/{sujeto.uuid}',
                headers={'X-SRCN-Token': token},
                timeout=5,
                verify=False
            )
            if r.ok:
                expediente_completo = r.json()
        except Exception as e:
            log.error(f"Error fetching expediente from {provincia_emisora}: {e}")

    response = {
        'encontrado': True,
        'warrant_activo': True,
        'sujeto_nombre': sujeto.nombre_completo,
        'expediente': sujeto.numero_expediente,
        'nivel_riesgo': sujeto.nivel_riesgo,
        'provincia_origen': provincia_emisora,
        'warrant_uuid': warrant.uuid,
        'nivel_urgencia': warrant.nivel_urgencia,
        'descripcion': warrant.descripcion[:500],
        'numero_judicial': warrant.numero_judicial,
        'juez_emisor': warrant.juez_emisor,
        'fecha_emision': warrant.fecha_emision.isoformat() if warrant.fecha_emision else None,
    }
    if expediente_completo:
        response['datos_sujeto'] = expediente_completo.get('datos_sujeto')
        response['detenciones']  = expediente_completo.get('detenciones', [])
        response['warrants']     = expediente_completo.get('warrants', [])

    return jsonify(response)


# ── RECIBIR WARRANT DEL NODO PROVINCIAL ──────────────────────
@provincial_bp.route('/recibir-warrant', methods=['POST'])
@requiere_token
def recibir_warrant():
    """
    Los nodos provinciales notifican aquí cuando emiten un nuevo warrant.
    El central lo registra en el índice nacional y propaga a todas las provincias.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    # Upsert in national index
    existente = Warrant.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        existente.estado = data.get('estado', existente.estado)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'actualizado'})

    sujeto = Sujeto.query.filter_by(uuid=data.get('sujeto_uuid')).first()
    if not sujeto:
        # Register minimal sujeto in national index
        sujeto = Sujeto(
            uuid=data['sujeto_uuid'],
            numero_expediente='IDX-' + data['sujeto_uuid'][:8],
            nombres=data.get('sujeto_nombres', ''),
            apellidos=data.get('sujeto_apellidos', ''),
            dni=data.get('sujeto_dni'),
            es_buscado=True,
            provincia_warrant=data.get('provincia_emisora'),
            sincronizado=True,
        )
        db.session.add(sujeto)
        db.session.flush()

    w = Warrant(
        uuid=data['uuid'],
        sujeto_id=sujeto.id,
        provincia_emisora=data['provincia_emisora'],
        descripcion=data.get('descripcion', ''),
        nivel_urgencia=data.get('nivel_urgencia', 'normal'),
        estado=data.get('estado', 'activo'),
        numero_judicial=data.get('numero_judicial'),
        juez_emisor=data.get('juez_emisor'),
        fecha_emision=_parse_dt(data.get('fecha_emision')) or datetime.utcnow(),
        sincronizado=True,
        propagado_nacional=True,
    )
    db.session.add(w)
    sujeto.es_buscado = True
    sujeto.provincia_warrant = w.provincia_emisora
    db.session.commit()

    # Propagate fugitive alert to ALL provinces simultaneously
    _propagar_alerta_nacional(data)

    return jsonify({'ok': True, 'accion': 'creado', 'propagado': True})


# ── RECIBIR SUJETO (sync desde provincia) ────────────────────
@provincial_bp.route('/recibir-sujeto', methods=['POST'])
@requiere_token
def recibir_sujeto():
    data = request.get_json()
    existente = Sujeto.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        existente.nivel_riesgo = data.get('nivel_riesgo', existente.nivel_riesgo)
        existente.es_buscado   = data.get('es_buscado', existente.es_buscado)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'actualizado'})
    s = Sujeto(
        uuid=data['uuid'],
        numero_expediente='IDX-' + data['uuid'][:8],
        nombres=data.get('nombres', ''),
        apellidos=data.get('apellidos', ''),
        dni=data.get('dni'),
        nivel_riesgo=data.get('nivel_riesgo', 'bajo'),
        es_buscado=data.get('es_buscado', False),
        provincia_warrant=data.get('provincia_warrant'),
        sincronizado=True,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({'ok': True, 'accion': 'creado'})


# ── PROPAGAR ALERTA A TODAS LAS PROVINCIAS ───────────────────
@provincial_bp.route('/propagar-alerta', methods=['POST'])
@requiere_token
def propagar_alerta_endpoint():
    """Manual trigger para re-propagar una alerta."""
    data = request.get_json()
    propagados = _propagar_alerta_nacional(data)
    return jsonify({'ok': True, 'propagado_a': propagados})


# ── ESTADÍSTICAS NACIONALES ───────────────────────────────────
@provincial_bp.route('/estadisticas', methods=['GET'])
@requiere_token
def estadisticas_nacionales():
    hace_30 = datetime.utcnow() - timedelta(days=30)
    return jsonify({
        'total_sujetos': Sujeto.query.filter_by(activo=True).count(),
        'warrants_activos': Warrant.query.filter_by(estado='activo').count(),
        'warrants_ejecutados_mes': Warrant.query.filter(
            Warrant.estado == 'ejecutado',
            Warrant.fecha_ejecucion >= hace_30).count(),
        'alertas_activas': AlertaProfugo.query.filter_by(activa=True).count(),
        'detenciones_mes': Detencion.query.filter(
            Detencion.fecha_detencion >= hace_30).count(),
        'timestamp': datetime.utcnow().isoformat(),
    })


# ── ESTADO DEL SERVIDOR CENTRAL ───────────────────────────────
@provincial_bp.route('/estado', methods=['GET'])
@requiere_token
def estado():
    provincias = Provincia.query.filter_by(activa=True).count()
    return jsonify({
        'ok': True,
        'nodo': 'CENTRAL-MINISTERIO',
        'timestamp': datetime.utcnow().isoformat(),
        'provincias_registradas': provincias,
        'warrants_activos': Warrant.query.filter_by(estado='activo').count(),
        'alertas_activas': AlertaProfugo.query.filter_by(activa=True).count(),
    })


# ── HELPERS ───────────────────────────────────────────────────
def _propagar_alerta_nacional(alerta_data):
    """
    Envía la alerta a todos los nodos provinciales en paralelo.
    Usa ThreadPoolExecutor para máxima velocidad — objetivo < 3s total.
    """
    provincias = Provincia.query.filter_by(activa=True).all()
    token = current_app.config.get('SYNC_API_TOKEN', '')
    propagados = []

    def _push(prov):
        if not prov.nodo_url:
            return None
        try:
            r = requests.post(
                prov.nodo_url.rstrip('/') + '/provincial/recibir-alerta',
                json=alerta_data,
                headers={'X-SRCN-Token': token},
                timeout=4,
                verify=False
            )
            if r.ok:
                return prov.codigo
        except Exception as e:
            log.warning(f"No se pudo alertar a provincia {prov.codigo}: {e}")
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_push, prov): prov for prov in provincias}
        for future in as_completed(futures, timeout=5):
            result = future.result()
            if result:
                propagados.append(result)

    log.info(f"Alerta propagada a {len(propagados)}/{len(provincias)} provincias")
    return propagados


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None
