"""
SRCN — Rutas: Warrants / Órdenes de Arresto
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json

from app.models.models import (db, Warrant, Sujeto, AlertaProfugo, RegistroSync)

warrants_bp = Blueprint('warrants', __name__)


@warrants_bp.route('/')
@login_required
def lista():
    estado = request.args.get('estado', 'activo')
    warrants = Warrant.query.filter_by(estado=estado).order_by(
        Warrant.fecha_emision.desc()).paginate(page=request.args.get('p', 1, type=int),
                                               per_page=25, error_out=False)
    return render_template('warrants/lista.html', warrants=warrants, estado=estado)


@warrants_bp.route('/nuevo/<int:sujeto_id>', methods=['GET', 'POST'])
@login_required
def nuevo(sujeto_id):
    if not current_user.puede_emitir_warrant:
        flash('Sin permisos para emitir órdenes de arresto.', 'danger')
        return redirect(url_for('sujetos.ver', id=sujeto_id))

    sujeto = Sujeto.query.get_or_404(sujeto_id)

    if request.method == 'POST':
        from flask import current_app
        warrant = Warrant(
            sujeto_id=sujeto_id,
            comisaria_emisora_id=current_user.comisaria_id,
            provincia_emisora=current_app.config.get('PROVINCE_CODE', 'BN'),
            emitido_por_id=current_user.id,
            numero_judicial=request.form.get('numero_judicial', '').strip() or None,
            juez_emisor=request.form.get('juez_emisor', '').strip() or None,
            tribunal=request.form.get('tribunal', '').strip() or None,
            descripcion=request.form.get('descripcion', '').strip(),
            nivel_urgencia=request.form.get('nivel_urgencia', 'normal'),
            estado='activo',
        )
        fecha_exp = request.form.get('fecha_expiracion')
        if fecha_exp:
            try:
                warrant.fecha_expiracion = datetime.strptime(fecha_exp, '%Y-%m-%d')
            except ValueError:
                pass

        db.session.add(warrant)

        # Mark sujeto as buscado
        sujeto.es_buscado = True
        sujeto.provincia_warrant = warrant.provincia_emisora

        db.session.flush()

        # Emit fugitive alert for propagation
        alerta = AlertaProfugo(
            warrant_uuid=warrant.uuid,
            sujeto_uuid=sujeto.uuid,
            sujeto_dni=sujeto.dni,
            sujeto_nombres=sujeto.nombres,
            sujeto_apellidos=sujeto.apellidos,
            huella_hash=sujeto.huella_hash,
            nivel_urgencia=warrant.nivel_urgencia,
            provincia_origen=warrant.provincia_emisora,
            descripcion_breve=warrant.descripcion[:500] if warrant.descripcion else None,
            activa=True,
        )
        db.session.add(alerta)

        sync = RegistroSync(
            comisaria_origen=current_user.comisaria.codigo if current_user.comisaria else 'LOCAL',
            tipo_dato='warrant',
            uuid_registro=warrant.uuid,
            accion='crear'
        )
        db.session.add(sync)
        db.session.commit()

        if current_app.config.get('INTRANET_MODE') and current_app.config.get('WARRANT_AUTO_PROPAGATE'):
            from app.utils.intranet_sync import encolar_registro, propagar_alerta_profugo
            encolar_registro('warrant', warrant.uuid)
            propagar_alerta_profugo(alerta.uuid)

        flash(f'Orden de arresto emitida. UUID: {warrant.uuid[:8]}…', 'success')
        return redirect(url_for('sujetos.ver', id=sujeto_id))

    return render_template('warrants/nuevo.html', sujeto=sujeto)


@warrants_bp.route('/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar(id):
    if not current_user.es_jefe:
        flash('Sin permisos para cancelar warrants.', 'danger')
        return redirect(url_for('warrants.lista'))
    w = Warrant.query.get_or_404(id)
    w.estado = 'cancelado'
    w.motivo_cancelacion = request.form.get('motivo', '').strip()
    sujeto = Sujeto.query.get(w.sujeto_id)
    if sujeto:
        sujeto.es_buscado = False
        sujeto.provincia_warrant = None
    # Deactivate alert
    alerta = AlertaProfugo.query.filter_by(warrant_uuid=w.uuid).first()
    if alerta:
        alerta.activa = False
    db.session.commit()
    flash('Warrant cancelado.', 'success')
    return redirect(url_for('sujetos.ver', id=w.sujeto_id))


@warrants_bp.route('/alertas')
@login_required
def alertas():
    alertas = AlertaProfugo.query.filter_by(activa=True).order_by(
        AlertaProfugo.creada_en.desc()).all()
    return render_template('warrants/alertas.html', alertas=alertas)
