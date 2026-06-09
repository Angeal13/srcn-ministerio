"""
SRCN — Rutas: Detenciones / Booking
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app.models.models import (db, Detencion, Sujeto, Cargo, CategoriaDelito,
                                Warrant, RegistroSync)

detenciones_bp = Blueprint('detenciones', __name__)


@detenciones_bp.route('/nueva', methods=['GET', 'POST'])
@detenciones_bp.route('/nueva/<int:sujeto_id>', methods=['GET', 'POST'])
@login_required
def nueva(sujeto_id=None):
    sujeto = None
    if sujeto_id:
        sujeto = Sujeto.query.get_or_404(sujeto_id)

    if request.method == 'POST':
        sid = request.form.get('sujeto_id', type=int)
        sujeto = Sujeto.query.get_or_404(sid)

        detencion = Detencion(
            sujeto_id=sid,
            comisaria_id=current_user.comisaria_id,
            agente_id=current_user.id,
            fecha_detencion=datetime.utcnow(),
            lugar_detencion=request.form.get('lugar_detencion', '').strip() or None,
            motivo=request.form.get('motivo', '').strip(),
            descripcion=request.form.get('descripcion', '').strip() or None,
            estado='activo',
        )
        # Link warrant if exists
        warrant_id = request.form.get('warrant_id', type=int)
        if warrant_id:
            detencion.warrant_id = warrant_id
            w = Warrant.query.get(warrant_id)
            if w and w.estado == 'activo':
                w.estado = 'ejecutado'
                w.fecha_ejecucion = datetime.utcnow()
                w.ejecutado_por_id = current_user.id
                w.comisaria_captura_id = current_user.comisaria_id
                sujeto.es_buscado = False
                sujeto.provincia_warrant = None

        db.session.add(detencion)
        db.session.flush()

        # Cargos
        categorias = request.form.getlist('categoria_id')
        for cat_id in categorias:
            if cat_id:
                cargo = Cargo(
                    detencion_id=detencion.id,
                    categoria_id=int(cat_id),
                    descripcion=request.form.get(f'cargo_desc_{cat_id}', '').strip() or None,
                    estado='pendiente'
                )
                db.session.add(cargo)

        sync = RegistroSync(
            comisaria_origen=current_user.comisaria.codigo if current_user.comisaria else 'LOCAL',
            tipo_dato='detencion',
            uuid_registro=detencion.uuid,
            accion='crear'
        )
        db.session.add(sync)
        db.session.commit()

        from flask import current_app
        if current_app.config.get('INTRANET_MODE'):
            from app.utils.intranet_sync import encolar_registro
            encolar_registro('detencion', detencion.uuid)

        flash(f'Detención registrada correctamente.', 'success')
        return redirect(url_for('detenciones.ver', id=detencion.id))

    categorias = CategoriaDelito.query.filter_by(activa=True).order_by(
        CategoriaDelito.categoria, CategoriaDelito.nombre).all()
    return render_template('detenciones/nueva.html',
                           sujeto=sujeto,
                           categorias=categorias)


@detenciones_bp.route('/<int:id>')
@login_required
def ver(id):
    detencion = Detencion.query.get_or_404(id)
    return render_template('detenciones/ver.html', detencion=detencion)


@detenciones_bp.route('/<int:id>/liberar', methods=['POST'])
@login_required
def liberar(id):
    if not current_user.es_jefe:
        flash('Sin permisos para procesar liberaciones.', 'danger')
        return redirect(url_for('detenciones.ver', id=id))
    detencion = Detencion.query.get_or_404(id)
    detencion.estado = 'liberado'
    detencion.fecha_liberacion = datetime.utcnow()
    detencion.motivo_liberacion = request.form.get('motivo_liberacion', '').strip()
    db.session.commit()
    flash('Detenido liberado. Registro actualizado.', 'success')
    return redirect(url_for('sujetos.ver', id=detencion.sujeto_id))
