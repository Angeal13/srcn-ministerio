"""
SRCN — API de Sincronización: Comisaría ↔ Nodo Provincial
Autenticación por token HMAC. Replica el patrón de Bioko Health.
"""
import hmac, hashlib, json
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from functools import wraps

from app.models.models import (db, Sujeto, Detencion, Cargo, Warrant,
                                AlertaProfugo, RegistroSync)

sync_bp = Blueprint('api_sync', __name__)


def requiere_api_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-SRCN-Token')
        expected = current_app.config.get('SYNC_API_TOKEN', '')
        if not token or not hmac.compare_digest(token, expected):
            return jsonify({'error': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated


@sync_bp.route('/estado', methods=['GET'])
@requiere_api_token
def estado():
    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()
    return jsonify({
        'ok': True,
        'comisaria': current_app.config.get('STATION_CODE'),
        'nombre': current_app.config.get('STATION_NAME'),
        'timestamp': datetime.utcnow().isoformat(),
        'pendientes_sync': pendientes
    })


# ── RECIBIR SUJETO ───────────────────────────────────────────
@sync_bp.route('/recibir-sujeto', methods=['POST'])
@requiere_api_token
def recibir_sujeto():
    """Recibe un perfil de sujeto desde otra comisaría o nodo provincial."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    existente = Sujeto.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        return jsonify({'ok': True, 'accion': 'ya_existe', 'id': existente.id})

    if data.get('dni'):
        conflicto = Sujeto.query.filter_by(dni=data['dni']).first()
        if conflicto:
            return jsonify({'ok': False, 'error': 'conflicto_dni',
                            'sujeto_existente_id': conflicto.id}), 409

    try:
        fecha_nac = None
        if data.get('fecha_nacimiento'):
            fecha_nac = datetime.strptime(data['fecha_nacimiento'], '%Y-%m-%d').date()

        sujeto = Sujeto(
            uuid=data['uuid'],
            numero_expediente=_asignar_numero_expediente(data.get('numero_expediente', '')),
            dni=data.get('dni'),
            nombres=data['nombres'],
            apellidos=data['apellidos'],
            fecha_nacimiento=fecha_nac,
            sexo=data.get('sexo'),
            nacionalidad=data.get('nacionalidad'),
            huella_hash=data.get('huella_hash'),
            direccion=data.get('direccion'),
            telefono=data.get('telefono'),
            nivel_riesgo=data.get('nivel_riesgo', 'bajo'),
            es_buscado=data.get('es_buscado', False),
            provincia_warrant=data.get('provincia_warrant'),
            sincronizado=True,
        )
        db.session.add(sujeto)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'creado', 'id': sujeto.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── RECIBIR WARRANT ──────────────────────────────────────────
@sync_bp.route('/recibir-warrant', methods=['POST'])
@requiere_api_token
def recibir_warrant():
    """Recibe una orden de arresto desde el nodo provincial / central."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    existente = Warrant.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        # Update status if changed
        if existente.estado != data.get('estado', existente.estado):
            existente.estado = data['estado']
            if data.get('fecha_ejecucion'):
                existente.fecha_ejecucion = datetime.fromisoformat(data['fecha_ejecucion'])
            db.session.commit()
        return jsonify({'ok': True, 'accion': 'actualizado'})

    sujeto = Sujeto.query.filter_by(uuid=data.get('sujeto_uuid')).first()
    if not sujeto:
        return jsonify({'error': 'sujeto_no_encontrado'}), 404

    try:
        warrant = Warrant(
            uuid=data['uuid'],
            sujeto_id=sujeto.id,
            provincia_emisora=data['provincia_emisora'],
            numero_judicial=data.get('numero_judicial'),
            juez_emisor=data.get('juez_emisor'),
            tribunal=data.get('tribunal'),
            delitos_asociados=json.dumps(data.get('delitos_asociados', [])),
            descripcion=data['descripcion'],
            nivel_urgencia=data.get('nivel_urgencia', 'normal'),
            estado=data.get('estado', 'activo'),
            sincronizado=True,
            propagado_nacional=True,
        )
        if data.get('fecha_emision'):
            warrant.fecha_emision = datetime.fromisoformat(data['fecha_emision'])
        if data.get('fecha_expiracion'):
            warrant.fecha_expiracion = datetime.fromisoformat(data['fecha_expiracion'])
        db.session.add(warrant)
        # Mark sujeto as buscado
        sujeto.es_buscado = (warrant.estado == 'activo')
        sujeto.provincia_warrant = warrant.provincia_emisora
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'creado', 'id': warrant.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── RECIBIR ALERTA PRÓFUGO ───────────────────────────────────
@sync_bp.route('/recibir-alerta-profugo', methods=['POST'])
@requiere_api_token
def recibir_alerta_profugo():
    """Recibe alerta ligera de prófugo buscado en otra provincia."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    existente = AlertaProfugo.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        existente.activa = data.get('activa', existente.activa)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'actualizado'})

    try:
        alerta = AlertaProfugo(
            uuid=data['uuid'],
            warrant_uuid=data['warrant_uuid'],
            sujeto_uuid=data['sujeto_uuid'],
            sujeto_dni=data.get('sujeto_dni'),
            sujeto_nombres=data.get('sujeto_nombres'),
            sujeto_apellidos=data.get('sujeto_apellidos'),
            huella_hash=data.get('huella_hash'),
            nivel_urgencia=data.get('nivel_urgencia', 'normal'),
            provincia_origen=data['provincia_origen'],
            descripcion_breve=data.get('descripcion_breve'),
            activa=True,
        )
        if data.get('expira_en'):
            alerta.expira_en = datetime.fromisoformat(data['expira_en'])
        db.session.add(alerta)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'creado', 'id': alerta.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── PUSH SYNC (comisaría → nodo provincial) ──────────────────
@sync_bp.route('/push-sync', methods=['POST'])
@requiere_api_token
def push_sync():
    """Recibe batch de registros desde una comisaría dependiente."""
    data = request.get_json()
    if not data or 'registros' not in data:
        return jsonify({'error': 'Payload inválido'}), 400

    resultados = []
    for reg in data['registros']:
        tipo = reg.get('tipo')
        try:
            if tipo == 'sujeto':
                r = _upsert_sujeto(reg['datos'])
            elif tipo == 'detencion':
                r = _upsert_detencion(reg['datos'])
            elif tipo == 'warrant':
                r = _upsert_warrant(reg['datos'])
            else:
                r = {'ok': False, 'error': f'tipo_desconocido: {tipo}'}
            resultados.append({'uuid': reg.get('uuid'), **r})
        except Exception as e:
            resultados.append({'uuid': reg.get('uuid'), 'ok': False, 'error': str(e)})

    db.session.commit()
    return jsonify({'ok': True, 'procesados': len(resultados), 'resultados': resultados})


# ── VERIFICAR WARRANT (consulta rápida) ──────────────────────
@sync_bp.route('/verificar-warrant/<sujeto_uuid>', methods=['GET'])
@requiere_api_token
def verificar_warrant(sujeto_uuid):
    """Comprobación rápida: ¿tiene este sujeto warrant activo?"""
    sujeto = Sujeto.query.filter_by(uuid=sujeto_uuid).first()
    if not sujeto:
        # Check by DNI
        dni = request.args.get('dni')
        if dni:
            sujeto = Sujeto.query.filter_by(dni=dni).first()

    if not sujeto:
        return jsonify({'encontrado': False, 'warrant_activo': False})

    warrant = Warrant.query.filter_by(sujeto_id=sujeto.id, estado='activo').first()
    return jsonify({
        'encontrado': True,
        'sujeto_uuid': sujeto.uuid,
        'sujeto_nombre': sujeto.nombre_completo,
        'warrant_activo': warrant is not None,
        'warrant_uuid': warrant.uuid if warrant else None,
        'provincia_emisora': warrant.provincia_emisora if warrant else None,
        'nivel_urgencia': warrant.nivel_urgencia if warrant else None,
    })


# ── HELPERS ──────────────────────────────────────────────────
def _asignar_numero_expediente(numero_original):
    existe = Sujeto.query.filter_by(numero_expediente=numero_original).first()
    if not existe:
        return numero_original
    import random
    return numero_original + '-' + str(random.randint(100, 999))


def _upsert_sujeto(datos):
    existente = Sujeto.query.filter_by(uuid=datos['uuid']).first()
    if existente:
        return {'ok': True, 'accion': 'ya_existe'}
    # minimal insert
    s = Sujeto(uuid=datos['uuid'], nombres=datos['nombres'],
               apellidos=datos['apellidos'],
               numero_expediente=_asignar_numero_expediente(datos.get('numero_expediente', datos['uuid'][:8])),
               sincronizado=True)
    db.session.add(s)
    return {'ok': True, 'accion': 'creado'}


def _upsert_detencion(datos):
    existente = Detencion.query.filter_by(uuid=datos['uuid']).first()
    if existente:
        return {'ok': True, 'accion': 'ya_existe'}
    sujeto = Sujeto.query.filter_by(uuid=datos['sujeto_uuid']).first()
    if not sujeto:
        return {'ok': False, 'error': 'sujeto_no_encontrado'}
    d = Detencion(uuid=datos['uuid'], sujeto_id=sujeto.id,
                  comisaria_id=1, agente_id=1,  # defaults — override per station
                  motivo=datos.get('motivo', ''), sincronizado=True)
    db.session.add(d)
    return {'ok': True, 'accion': 'creado'}


def _upsert_warrant(datos):
    existente = Warrant.query.filter_by(uuid=datos['uuid']).first()
    if existente:
        existente.estado = datos.get('estado', existente.estado)
        return {'ok': True, 'accion': 'actualizado'}
    sujeto = Sujeto.query.filter_by(uuid=datos['sujeto_uuid']).first()
    if not sujeto:
        return {'ok': False, 'error': 'sujeto_no_encontrado'}
    w = Warrant(uuid=datos['uuid'], sujeto_id=sujeto.id,
                provincia_emisora=datos['provincia_emisora'],
                descripcion=datos.get('descripcion', ''),
                estado=datos.get('estado', 'activo'), sincronizado=True)
    db.session.add(w)
    return {'ok': True, 'accion': 'creado'}
