"""SRCN — Transferencias de detenidos entre comisarías"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from app.models.models import db, TransferenciaDetenido, Sujeto, Detencion, RegistroSync

transferencias_bp = Blueprint('transferencias', __name__)

@transferencias_bp.route('/nueva/<int:detencion_id>', methods=['GET', 'POST'])
@login_required
def nueva(detencion_id):
    if not current_user.es_jefe:
        from flask import abort
        abort(403)
    detencion = Detencion.query.get_or_404(detencion_id)
    sujeto = detencion.sujeto
    if request.method == 'POST':
        from flask import current_app
        t = TransferenciaDetenido(
            sujeto_id=sujeto.id,
            detencion_id=detencion.id,
            comisaria_origen_codigo=current_user.comisaria.codigo if current_user.comisaria else 'LOCAL',
            provincia_origen=current_app.config.get('PROVINCE_CODE', 'BN'),
            comisaria_destino_codigo=request.form.get('comisaria_destino_codigo', '').strip(),
            provincia_destino=request.form.get('provincia_destino', '').strip(),
            motivo=request.form.get('motivo', '').strip(),
            urgente=request.form.get('urgente') == 'on',
            iniciada_por_id=current_user.id,
            estado='iniciada',
        )
        db.session.add(t)
        detencion.estado = 'trasladado'
        db.session.commit()
        flash('Transferencia iniciada correctamente.', 'success')
        return redirect(url_for('sujetos.ver', id=sujeto.id))
    return render_template('transferencias/nueva.html', detencion=detencion, sujeto=sujeto)

@transferencias_bp.route('/estado')
@login_required
def estado():
    transferencias = TransferenciaDetenido.query.order_by(
        TransferenciaDetenido.iniciada_en.desc()).limit(50).all()
    return render_template('transferencias/estado.html', transferencias=transferencias)
