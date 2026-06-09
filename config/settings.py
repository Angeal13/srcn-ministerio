"""
SRCN — Configuración del Sistema
"""
import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'srcn-dev-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    BABEL_DEFAULT_LOCALE = 'es'

    STATION_CODE = os.environ.get('STATION_CODE', 'COM-BN-001')
    STATION_NAME = os.environ.get('STATION_NAME', 'Comisaría Central Malabo')
    STATION_TYPE = os.environ.get('STATION_TYPE', 'comisaria')  # comisaria | puesto | cuartel
    PROVINCE_CODE = os.environ.get('PROVINCE_CODE', 'BN')

    STATION_MODE = os.environ.get('STATION_MODE', 'local_station')
    # Modes: local_station | intranet_station | provincial_node | central_server | annobon_node

    LAN_HOST = os.environ.get('LAN_HOST', '0.0.0.0')
    LAN_PORT = int(os.environ.get('LAN_PORT', '5000'))
    LAN_URL  = os.environ.get('LAN_URL', '')

    SYNC_ENABLED       = os.environ.get('SYNC_ENABLED', 'false').lower() == 'true'
    PROVINCIAL_NODE_URL = os.environ.get('PROVINCIAL_NODE_URL', '')
    SYNC_API_TOKEN     = os.environ.get('SYNC_API_TOKEN', '')
    SYNC_HOUR          = int(os.environ.get('SYNC_HOUR', '2'))
    SYNC_MINUTE        = int(os.environ.get('SYNC_MINUTE', '0'))

    INTRANET_MODE          = os.environ.get('INTRANET_MODE', 'false').lower() == 'true'
    INTRANET_CENTRAL_URL   = os.environ.get('INTRANET_CENTRAL_URL', '')
    INTRANET_PULL_INTERVAL = int(os.environ.get('INTRANET_PULL_INTERVAL', '30'))
    INTRANET_RETRY_INTERVAL = int(os.environ.get('INTRANET_RETRY_INTERVAL', '10'))
    INTRANET_WRITE_THROUGH = os.environ.get('INTRANET_WRITE_THROUGH', 'false').lower() == 'true'

    # Warrant alert propagation — push to all provinces on new warrant
    WARRANT_AUTO_PROPAGATE = os.environ.get('WARRANT_AUTO_PROPAGATE', 'true').lower() == 'true'

    # Biometric fingerprint reader
    BIOMETRIC_ENABLED = os.environ.get('BIOMETRIC_ENABLED', 'false').lower() == 'true'
    BIOMETRIC_DEVICE  = os.environ.get('BIOMETRIC_DEVICE', '/dev/usb/fingerprint0')

    SESSION_TYPE      = 'filesystem'
    SESSION_FILE_DIR  = os.path.join(BASE_DIR, '..', 'flask_sessions')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = 28800

    UPLOAD_FOLDER     = os.path.join(BASE_DIR, '..', 'uploads')
    REPORTS_FOLDER    = os.path.join(BASE_DIR, '..', 'reports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URL') or
        'sqlite:///' + os.path.join(BASE_DIR, '..', 'srcn_dev.db')
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'sqlite:///' + os.path.join(BASE_DIR, '..', 'srcn.db')
    )
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '10'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '20'))
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 1800
    SQLALCHEMY_POOL_PRE_PING = True


class IntranetStationConfig(ProductionConfig):
    STATION_MODE    = 'intranet_station'
    INTRANET_MODE   = True
    SYNC_ENABLED    = True
    SYNC_HOUR       = 3
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '15'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '25'))


class ProvincialNodeConfig(ProductionConfig):
    STATION_MODE    = 'provincial_node'
    INTRANET_MODE   = True
    SYNC_ENABLED    = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'mysql+pymysql://srcn_user:password@localhost/srcn_provincial'
    )
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '40'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '60'))
    SQLALCHEMY_POOL_RECYCLE = 900
    CACHE_EXPEDIENTE_DIAS   = int(os.environ.get('CACHE_EXPEDIENTE_DIAS', '30'))
    CENTRAL_SERVER_URL      = os.environ.get('CENTRAL_SERVER_URL', '')
    PROVINCIAL_NODE_URL     = ''


class CentralServerConfig(ProductionConfig):
    STATION_MODE    = 'central_server'
    INTRANET_MODE   = True
    SYNC_ENABLED    = False
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'mysql+pymysql://srcn_user:password@localhost/srcn_nacional'
    )
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '60'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '80'))
    SQLALCHEMY_POOL_RECYCLE = 900


class AnnobonNodeConfig(ProvincialNodeConfig):
    STATION_MODE         = 'annobon_node'
    SYNC_HOUR            = 3
    SYNC_MINUTE          = 0
    ANNOBON_SYNC_MODE    = os.environ.get('ANNOBON_SYNC_MODE', 'weekly')
    INTRANET_PULL_INTERVAL = 300


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SYNC_ENABLED     = False
    INTRANET_MODE    = False


config = {
    'development':     DevelopmentConfig,
    'production':      ProductionConfig,
    'intranet_station': IntranetStationConfig,
    'provincial_node': ProvincialNodeConfig,
    'central':         CentralServerConfig,
    'annobon_node':    AnnobonNodeConfig,
    'testing':         TestingConfig,
    'default':         DevelopmentConfig,
}
