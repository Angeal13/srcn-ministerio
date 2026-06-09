"""
SRCN — Rutas: Sujetos (Perfiles Criminales)
Equivalente a pacientes.py en Bioko Health.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from datetime import datetime, date

from app.models.models import (db, Sujeto, Detencion, Warrant, AlertaProfugo,
                                Distrito, RegistroSync, Comisaria)

sujetos_bp = Blueprint('sujetos', __name__)


def generar_numero_expediente():
    anio = datetime.now().year
    ultimo = Sujeto.query.filter(
        Sujeto.numero_expediente.like(f'EXP-{anio}%')
    ).count()
    return f'EXP-{anio}{str(ultimo + 1).zfill(5)}'


@sujetos_bp.route('/dashboard')
@login_required
def dashboard():
    hoy = date.today()
    detenciones_hoy = Detencion.query.filter(
        func.date(Detencion.fecha_detencion) == hoy
    ).count()
    total_sujetos = Sujeto.query.filter_by(activo=True).count()
    nuevos_hoy = Sujeto.query.filter(
        func.date(Sujeto.creado_en) == hoy
    ).count()
    warrants_activos = Warrant.query.filter_by(estado='activo').count()
    alertas_profugo = AlertaProfugo.query.filter_by(activa=True).count()

    ultimas_detenciones = (Detencion.query
                           .join(Sujeto)
                           .order_by(Detencion.fecha_detencion.desc())
                           .limit(10).all())

    alertas = AlertaProfugo.query.filter_by(activa=True).order_by(
        AlertaProfugo.creada_en.desc()
    ).limit(5).all()

    return render_template('sujetos/dashboard.html',
                           detenciones_hoy=detenciones_hoy,
                           total_sujetos=total_sujetos,
                           nuevos_hoy=nuevos_hoy,
                           warrants_activos=warrants_activos,
                           alertas_profugo=alertas_profugo,
                           ultimas_detenciones=ultimas_detenciones,
                           alertas=alertas)


@sujetos_bp.route('/')
@login_required
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    busqueda = request.args.get('q', '').strip()
    nivel_riesgo = request.args.get('nivel_riesgo', '').strip()
    solo_buscados = request.args.get('buscados', False, type=bool)

    query = Sujeto.query.filter_by(activo=True)

    if busqueda:
        query = query.filter(or_(
            Sujeto.nombres.ilike(f'%{busqueda}%'),
            Sujeto.apellidos.ilike(f'%{busqueda}%'),
            Sujeto.numero_expediente.ilike(f'%{busqueda}%'),
            Sujeto.dni.ilike(f'%{busqueda}%'),
        ))
    if nivel_riesgo:
        query = query.filter_by(nivel_riesgo=nivel_riesgo)
    if solo_buscados:
        query = query.filter_by(es_buscado=True)

    sujetos = query.order_by(Sujeto.apellidos).paginate(
        page=pagina, per_page=25, error_out=False
    )
    return render_template('sujetos/lista.html',
                           sujetos=sujetos,
                           busqueda=busqueda,
                           nivel_riesgo=nivel_riesgo,
                           solo_buscados=solo_buscados)


@sujetos_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        dni = request.form.get('dni', '').strip() or None
        if dni and Sujeto.query.filter_by(dni=dni).first():
            flash('Ya existe un sujeto con ese número de documento.', 'danger')
            return redirect(url_for('sujetos.nuevo'))

        fecha_nac_str = request.form.get('fecha_nacimiento')
        fecha_nac = None
        if fecha_nac_str:
            try:
                fecha_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Fecha de nacimiento inválida.', 'danger')
                return redirect(url_for('sujetos.nuevo'))

        sujeto = Sujeto(
            numero_expediente=generar_numero_expediente(),
            dni=dni,
            nombres=request.form.get('nombres', '').strip(),
            apellidos=request.form.get('apellidos', '').strip(),
            fecha_nacimiento=fecha_nac,
            sexo=request.form.get('sexo'),
            nacionalidad=request.form.get('nacionalidad', '').strip() or None,
            direccion=request.form.get('direccion', '').strip() or None,
            telefono=request.form.get('telefono', '').strip() or None,
            nivel_riesgo=request.form.get('nivel_riesgo', 'bajo'),
            creado_por_id=current_user.id,
            comisaria_origen_id=current_user.comisaria_id,
        )
        db.session.add(sujeto)
        db.session.flush()

        sync = RegistroSync(
            comisaria_origen=current_user.comisaria.codigo if current_user.comisaria else 'LOCAL',
            tipo_dato='sujeto',
            uuid_registro=sujeto.uuid,
            accion='crear'
        )
        db.session.add(sync)
        db.session.commit()

        from flask import current_app
        if current_app.config.get('INTRANET_MODE'):
            from app.utils.intranet_sync import encolar_registro
            encolar_registro('sujeto', sujeto.uuid)

        flash(f'Sujeto registrado. Expediente: {sujeto.numero_expediente}', 'success')
        return redirect(url_for('sujetos.ver', id=sujeto.id))

    distritos = Distrito.query.order_by(Distrito.nombre).all()
    return render_template('sujetos/nuevo.html', distritos=distritos)


@sujetos_bp.route('/<int:id>')
@login_required
def ver(id):
    sujeto = Sujeto.query.get_or_404(id)
    detenciones = (sujeto.detenciones
                   .order_by(Detencion.fecha_detencion.desc())
                   .limit(20).all())
    warrants = sujeto.warrants.order_by(Warrant.fecha_emision.desc()).all()
    warrant_activo = Warrant.query.filter_by(
        sujeto_id=id, estado='activo').first()

    return render_template('sujetos/ver.html',
                           sujeto=sujeto,
                           detenciones=detenciones,
                           warrants=warrants,
                           warrant_activo=warrant_activo)


@sujetos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    sujeto = Sujeto.query.get_or_404(id)
    if not current_user.es_jefe:
        flash('Sin permisos para editar perfiles criminales.', 'danger')
        return redirect(url_for('sujetos.ver', id=id))

    if request.method == 'POST':
        fecha_nac_str = request.form.get('fecha_nacimiento')
        if fecha_nac_str:
            try:
                sujeto.fecha_nacimiento = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Fecha inválida.', 'danger')
                return redirect(url_for('sujetos.editar', id=id))

        sujeto.nombres = request.form.get('nombres', '').strip()
        sujeto.apellidos = request.form.get('apellidos', '').strip()
        sujeto.sexo = request.form.get('sexo')
        sujeto.nacionalidad = request.form.get('nacionalidad', '').strip() or None
        sujeto.direccion = request.form.get('direccion', '').strip() or None
        sujeto.telefono = request.form.get('telefono', '').strip() or None
        sujeto.nivel_riesgo = request.form.get('nivel_riesgo', 'bajo')
        sujeto.sincronizado = False
        db.session.commit()
        flash('Perfil actualizado.', 'success')
        return redirect(url_for('sujetos.ver', id=id))

    distritos = Distrito.query.order_by(Distrito.nombre).all()
    return render_template('sujetos/editar.html', sujeto=sujeto, distritos=distritos)


@sujetos_bp.route('/buscar-ajax')
@login_required
def buscar_ajax():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    sujetos = Sujeto.query.filter(
        Sujeto.activo == True,
        or_(
            Sujeto.nombres.ilike(f'%{q}%'),
            Sujeto.apellidos.ilike(f'%{q}%'),
            Sujeto.numero_expediente.ilike(f'%{q}%'),
            Sujeto.dni.ilike(f'%{q}%'),
        )
    ).limit(10).all()
    return jsonify([{
        'id': s.id,
        'numero_expediente': s.numero_expediente,
        'nombre': s.nombre_completo,
        'edad': s.edad,
        'sexo': s.sexo,
        'dni': s.dni or '',
        'nivel_riesgo': s.nivel_riesgo,
        'es_buscado': s.es_buscado,
    } for s in sujetos])


@sujetos_bp.route('/verificar-dni')
@login_required
def verificar_dni():
    """Verificación rápida de campo: DNI → antecedentes + warrant."""
    dni = request.args.get('dni', '').strip()
    if not dni or len(dni) < 3:
        return jsonify({'encontrado': False})

    sujeto = Sujeto.query.filter_by(dni=dni).first()
    if not sujeto:
        # Check remote via nodo provincial
        return jsonify({'encontrado': False, 'sin_antecedentes_locales': True})

    warrant = Warrant.query.filter_by(sujeto_id=sujeto.id, estado='activo').first()
    return jsonify({
        'encontrado': True,
        'sujeto_id': sujeto.id,
        'nombre': sujeto.nombre_completo,
        'expediente': sujeto.numero_expediente,
        'nivel_riesgo': sujeto.nivel_riesgo,
        'warrant_activo': warrant is not None,
        'warrant_uuid': warrant.uuid if warrant else None,
        'nivel_urgencia': warrant.nivel_urgencia if warrant else None,
        'provincia_emisora': warrant.provincia_emisora if warrant else None,
    })
