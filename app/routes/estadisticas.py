"""SRCN — Estadísticas"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models.models import db, Detencion, Sujeto, Warrant, CategoriaDelito, Cargo

estadisticas_bp = Blueprint('estadisticas', __name__)

@estadisticas_bp.route('/')
@login_required
def index():
    if not current_user.es_jefe:
        from flask import abort
        abort(403)
    hace_30 = datetime.utcnow() - timedelta(days=30)
    detenciones_mes = Detencion.query.filter(Detencion.fecha_detencion >= hace_30).count()
    warrants_activos = Warrant.query.filter_by(estado='activo').count()
    warrants_ejecutados_mes = Warrant.query.filter(
        Warrant.estado == 'ejecutado',
        Warrant.fecha_ejecucion >= hace_30
    ).count()
    top_delitos = (db.session.query(
        CategoriaDelito.nombre, func.count(Cargo.id).label('total')
    ).join(Cargo).join(Detencion)
     .filter(Detencion.fecha_detencion >= hace_30)
     .group_by(CategoriaDelito.id)
     .order_by(func.count(Cargo.id).desc())
     .limit(8).all())
    return render_template('estadisticas/index.html',
                           detenciones_mes=detenciones_mes,
                           warrants_activos=warrants_activos,
                           warrants_ejecutados_mes=warrants_ejecutados_mes,
                           top_delitos=top_delitos)
