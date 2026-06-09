"""SRCN — App Factory (Servidor Central / Ministerio del Interior)"""
import os, logging
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.models.models import db, bcrypt, Usuario
from config.settings import config

migrate = Migrate(); login_manager = LoginManager()
sess = Session(); limiter = Limiter(key_func=get_remote_address, default_limits=[])
log = logging.getLogger('srcn.central')


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'central')
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    if not app.debug:
        log_dir = os.path.join(app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, 'srcn_central.log'))
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        app.logger.addHandler(fh)

    for folder in ['UPLOAD_FOLDER', 'REPORTS_FOLDER', 'SESSION_FILE_DIR']:
        path = app.config.get(folder)
        if path: os.makedirs(path, exist_ok=True)

    db.init_app(app); bcrypt.init_app(app); migrate.init_app(app, db)
    sess.init_app(app); limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Acceso restringido — Ministerio del Interior.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.sujetos import sujetos_bp
    from app.routes.warrants import warrants_bp
    from app.routes.estadisticas import estadisticas_bp
    from app.routes.admin import admin_bp
    from app.routes.api_sync import sync_bp
    from app.routes.red import red_bp
    from app.routes.nodo_provincial import provincial_bp   # ← central logic

    app.register_blueprint(auth_bp,        url_prefix='/auth')
    app.register_blueprint(sujetos_bp,      url_prefix='/sujetos')
    app.register_blueprint(warrants_bp,     url_prefix='/warrants')
    app.register_blueprint(estadisticas_bp, url_prefix='/estadisticas')
    app.register_blueprint(admin_bp,        url_prefix='/admin')
    app.register_blueprint(sync_bp,         url_prefix='/api/sync')
    app.register_blueprint(red_bp,          url_prefix='/red')
    # National API — provinces call these endpoints
    app.register_blueprint(provincial_bp,   url_prefix='/api/nacional')

    limiter.limit("10 per minute")(auth_bp)

    from app.utils.sync_scheduler import init_sync
    init_sync(app)
    from app.utils.intranet_sync import init_intranet
    init_intranet(app)

    @app.errorhandler(404)
    def not_found(e): return render_template('errors/404.html'), 404
    @app.errorhandler(403)
    def forbidden(e): return render_template('errors/403.html'), 403
    @app.errorhandler(500)
    def server_error(e):
        log.exception("Internal server error")
        return render_template('errors/500.html'), 500
    @app.errorhandler(429)
    def too_many(e): return render_template('errors/429.html'), 429

    @app.route('/')
    def index(): return redirect(url_for('provincial.dashboard'))

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from datetime import datetime
        from app.models.models import AlertaProfugo, Warrant
        alertas_count = warrants_count = 0
        try:
            alertas_count = AlertaProfugo.query.filter_by(activa=True).count()
            warrants_count = Warrant.query.filter_by(estado='activo').count()
        except Exception: pass
        return dict(current_user=current_user,
                    station_name=app.config.get('STATION_NAME', 'SRCN — Ministerio del Interior'),
                    station_code=app.config.get('STATION_CODE', 'CENTRAL'),
                    station_mode=app.config.get('STATION_MODE', 'central_server'),
                    province_code='NACIONAL',
                    lan_url=app.config.get('LAN_URL', ''),
                    intranet_mode=app.config.get('INTRANET_MODE', True),
                    alertas_count=alertas_count,
                    warrants_count=warrants_count,
                    now=datetime.utcnow)
    return app
