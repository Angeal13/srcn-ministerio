"""SRCN — Autenticación"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.models import db, Usuario

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('sujetos.dashboard'))
    if request.method == 'POST':
        usuario = Usuario.query.filter_by(
            nombre_usuario=request.form.get('nombre_usuario', '').strip()
        ).first()
        if usuario and usuario.activo and usuario.check_password(request.form.get('password', '')):
            from datetime import datetime
            usuario.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            login_user(usuario, remember=False)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('sujetos.dashboard'))
        flash('Credenciales incorrectas o cuenta desactivada.', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        if not current_user.check_password(request.form.get('password_actual', '')):
            flash('Contraseña actual incorrecta.', 'danger')
            return redirect(url_for('auth.cambiar_password'))
        nueva = request.form.get('nueva_password', '')
        if len(nueva) < 8:
            flash('La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
            return redirect(url_for('auth.cambiar_password'))
        current_user.set_password(nueva)
        db.session.commit()
        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for('sujetos.dashboard'))
    return render_template('auth/cambiar_password.html')
