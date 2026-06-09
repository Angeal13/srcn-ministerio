"""SRCN — Panel de red / estado de nodos"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models.models import NodoComisaria, RegistroSync

red_bp = Blueprint('red', __name__)

@red_bp.route('/panel')
@login_required
def panel():
    if not current_user.es_admin:
        from flask import abort
        abort(403)
    nodos = NodoComisaria.query.all()
    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()
    errores = RegistroSync.query.filter_by(estado='error').count()
    return render_template('red/panel.html', nodos=nodos,
                           pendientes=pendientes, errores=errores)

@red_bp.route('/estado-json')
@login_required
def estado_json():
    from datetime import datetime
    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()
    return jsonify({'ok': True, 'pendientes': pendientes,
                    'timestamp': datetime.utcnow().isoformat()})
