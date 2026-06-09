"""SRCN — Administración"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.models import db, Usuario, Comisaria, CategoriaDelito

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    from functools import wraps
    from flask import abort
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@login_required
@admin_required
def panel():
    usuarios = Usuario.query.count()
    comisarias = Comisaria.query.count()
    return render_template('admin/panel.html', usuarios=usuarios, comisarias=comisarias)

@admin_bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    return render_template('admin/usuarios.html',
                           usuarios=Usuario.query.order_by(Usuario.nombre_completo).all())

@admin_bp.route('/nuevo-usuario', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo_usuario():
    if request.method == 'POST':
        u = Usuario(
            nombre_usuario=request.form.get('nombre_usuario', '').strip(),
            nombre_completo=request.form.get('nombre_completo', '').strip(),
            email=request.form.get('email', '').strip() or None,
            rol=request.form.get('rol', 'agente'),
            comisaria_id=request.form.get('comisaria_id', type=int) or None,
            numero_placa=request.form.get('numero_placa', '').strip() or None,
        )
        u.set_password(request.form.get('password', ''))
        db.session.add(u)
        db.session.commit()
        flash(f'Usuario {u.nombre_usuario} creado.', 'success')
        return redirect(url_for('admin.usuarios'))
    comisarias = Comisaria.query.order_by(Comisaria.nombre).all()
    return render_template('admin/nuevo_usuario.html', comisarias=comisarias)
