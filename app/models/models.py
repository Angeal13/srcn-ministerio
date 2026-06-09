"""
SRCN — Sistema de Registro Criminal Nacional
Módulo: Comisaría (Nodo Local)
Nivel 1 de 3 — SQLite local, sync hacia nodo provincial
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
import uuid

db = SQLAlchemy()
bcrypt = Bcrypt()


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────

class Provincia(db.Model):
    __tablename__ = 'provincias'
    id      = db.Column(db.Integer, primary_key=True)
    codigo  = db.Column(db.String(10), unique=True, nullable=False)
    nombre  = db.Column(db.String(100), nullable=False)
    sede    = db.Column(db.String(100))
    activa  = db.Column(db.Boolean, default=True)
    nodo_url = db.Column(db.String(255))  # URL del nodo provincial


class Distrito(db.Model):
    __tablename__ = 'distritos'
    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(100), nullable=False)
    codigo      = db.Column(db.String(20), unique=True, nullable=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey('provincias.id'))
    latitud     = db.Column(db.Float)
    longitud    = db.Column(db.Float)


# ─────────────────────────────────────────────
# COMISARÍA (ESTACIÓN POLICIAL)
# ─────────────────────────────────────────────

class Comisaria(db.Model):
    __tablename__ = 'comisarias'
    id          = db.Column(db.Integer, primary_key=True)
    codigo      = db.Column(db.String(30), unique=True, nullable=False)
    nombre      = db.Column(db.String(150), nullable=False)
    tipo        = db.Column(db.String(30), nullable=False)  # comisaria | puesto | cuartel
    distrito_id = db.Column(db.Integer, db.ForeignKey('distritos.id'))
    provincia_id = db.Column(db.Integer, db.ForeignKey('provincias.id'))
    latitud     = db.Column(db.Float)
    longitud    = db.Column(db.Float)
    telefono    = db.Column(db.String(30))
    activa      = db.Column(db.Boolean, default=True)
    es_nodo_local = db.Column(db.Boolean, default=False)

    usuarios    = db.relationship('Usuario', backref='comisaria', lazy='dynamic')
    detenidos   = db.relationship('Detenido', backref='comisaria_registro', lazy='dynamic')


# ─────────────────────────────────────────────
# USUARIOS Y ROLES
# ─────────────────────────────────────────────

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    nombre_usuario  = db.Column(db.String(80), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=False)
    email           = db.Column(db.String(120))
    password_hash   = db.Column(db.String(255), nullable=False)
    rol             = db.Column(db.String(30), nullable=False)
    # Roles: superadmin | jefe | agente | inspector | readonly
    comisaria_id    = db.Column(db.Integer, db.ForeignKey('comisarias.id'))
    activo          = db.Column(db.Boolean, default=True)
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso   = db.Column(db.DateTime)
    numero_placa    = db.Column(db.String(20))

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    @property
    def es_jefe(self):
        return self.rol in ('superadmin', 'jefe')

    @property
    def es_admin(self):
        return self.rol in ('superadmin',)

    @property
    def puede_emitir_warrant(self):
        return self.rol in ('superadmin', 'jefe', 'inspector')


# ─────────────────────────────────────────────
# SUJETO (PERFIL CRIMINAL)
# ─────────────────────────────────────────────

class Sujeto(db.Model):
    """
    Perfil criminal de un individuo en el sistema SRCN.
    Equivalente al Paciente en Bioko Health.
    Identificado por DNI + hash biométrico.
    """
    __tablename__ = 'sujetos'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    # Identificación
    numero_expediente = db.Column(db.String(20), unique=True, nullable=False)
    dni             = db.Column(db.String(30), unique=True)
    nombres         = db.Column(db.String(100), nullable=False)
    apellidos       = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date)
    sexo            = db.Column(db.String(1))  # M / F
    nacionalidad    = db.Column(db.String(50))
    # Biometría
    huella_hash     = db.Column(db.String(128))   # Hash SHA-512 de la plantilla dactilar
    foto            = db.Column(db.String(255))   # Path al archivo de foto
    # Domicilio conocido
    distrito_id     = db.Column(db.Integer, db.ForeignKey('distritos.id'))
    direccion       = db.Column(db.String(255))
    telefono        = db.Column(db.String(30))
    # Clasificación
    nivel_riesgo    = db.Column(db.String(20), default='bajo')  # bajo | medio | alto | critico
    es_buscado      = db.Column(db.Boolean, default=False)      # Warrant activo en cualquier provincia
    provincia_warrant = db.Column(db.String(10))                # Provincia que emitió el warrant activo
    # Metadata
    activo          = db.Column(db.Boolean, default=True)
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    comisaria_origen_id = db.Column(db.Integer, db.ForeignKey('comisarias.id'))
    sincronizado    = db.Column(db.Boolean, default=False)
    hash_integridad = db.Column(db.String(64))

    detenciones     = db.relationship('Detencion', backref='sujeto', lazy='dynamic',
                                       order_by='Detencion.fecha_detencion.desc()')
    warrants        = db.relationship('Warrant', backref='sujeto', lazy='dynamic')

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        today = date.today()
        born = self.fecha_nacimiento
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def __repr__(self):
        return f'<Sujeto {self.numero_expediente}: {self.nombre_completo}>'


# ─────────────────────────────────────────────
# DETENCIÓN / BOOKING
# ─────────────────────────────────────────────

class Detencion(db.Model):
    """
    Registro de cada detención/booking.
    Equivalente a Consulta en Bioko Health.
    """
    __tablename__ = 'detenciones'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    # Sujeto y lugar
    sujeto_id       = db.Column(db.Integer, db.ForeignKey('sujetos.id'), nullable=False)
    comisaria_id    = db.Column(db.Integer, db.ForeignKey('comisarias.id'), nullable=False)
    agente_id       = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    # Datos del evento
    fecha_detencion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lugar_detencion = db.Column(db.String(255))
    motivo          = db.Column(db.Text, nullable=False)
    descripcion     = db.Column(db.Text)
    # Cargos
    cargos          = db.relationship('Cargo', backref='detencion', lazy='dynamic')
    # Estado
    estado          = db.Column(db.String(20), default='activo')
    # activo | liberado | trasladado | juicio | condenado
    fecha_liberacion = db.Column(db.DateTime)
    motivo_liberacion = db.Column(db.String(255))
    # Warrant relacionado
    warrant_id      = db.Column(db.Integer, db.ForeignKey('warrants.id'))
    # Sync
    sincronizado    = db.Column(db.Boolean, default=False)
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)

    agente          = db.relationship('Usuario', foreign_keys=[agente_id])
    comisaria       = db.relationship('Comisaria', foreign_keys=[comisaria_id])


# ─────────────────────────────────────────────
# CATEGORÍAS DE DELITO
# ─────────────────────────────────────────────

class CategoriaDelito(db.Model):
    """Catálogo de tipos de delito. Equivalente a Enfermedad/ICD-10."""
    __tablename__ = 'categorias_delito'
    id              = db.Column(db.Integer, primary_key=True)
    codigo          = db.Column(db.String(10), unique=True, nullable=False)
    nombre          = db.Column(db.String(255), nullable=False)
    descripcion     = db.Column(db.Text)
    categoria       = db.Column(db.String(100))    # contra_personas | propiedad | narco | orden_publico
    gravedad        = db.Column(db.String(20))     # falta | delito_menor | delito_grave | crimen
    es_notificable  = db.Column(db.Boolean, default=False)  # Notificación al Ministerio
    activa          = db.Column(db.Boolean, default=True)

    cargos          = db.relationship('Cargo', backref='categoria', lazy='dynamic')


class Cargo(db.Model):
    """Cargo específico dentro de una detención."""
    __tablename__ = 'cargos'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    detencion_id    = db.Column(db.Integer, db.ForeignKey('detenciones.id'), nullable=False)
    categoria_id    = db.Column(db.Integer, db.ForeignKey('categorias_delito.id'), nullable=False)
    descripcion     = db.Column(db.Text)
    estado          = db.Column(db.String(20), default='pendiente')  # pendiente | confirmado | retirado
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# WARRANTS / ÓRDENES DE ARRESTO
# ─────────────────────────────────────────────

class Warrant(db.Model):
    """
    Orden de arresto activa.
    Equivalente a AlertaEpidemiologica en Bioko Health.
    Se propaga a todas las provincias como alerta ligera.
    """
    __tablename__ = 'warrants'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    sujeto_id       = db.Column(db.Integer, db.ForeignKey('sujetos.id'), nullable=False)
    # Emisión
    comisaria_emisora_id = db.Column(db.Integer, db.ForeignKey('comisarias.id'))
    provincia_emisora = db.Column(db.String(10), nullable=False)
    emitido_por_id  = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    # Datos legales
    numero_judicial = db.Column(db.String(50))    # Número de expediente judicial
    juez_emisor     = db.Column(db.String(150))
    tribunal        = db.Column(db.String(150))
    delitos_asociados = db.Column(db.Text)        # JSON array de códigos de delito
    descripcion     = db.Column(db.Text, nullable=False)
    nivel_urgencia  = db.Column(db.String(20), default='normal')  # normal | urgente | critico
    # Vigencia
    fecha_emision   = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_expiracion = db.Column(db.DateTime)
    # Estado del ciclo de vida
    estado          = db.Column(db.String(20), default='activo')
    # activo | ejecutado | cancelado | expirado
    fecha_ejecucion = db.Column(db.DateTime)
    ejecutado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    comisaria_captura_id = db.Column(db.Integer, db.ForeignKey('comisarias.id'))
    provincia_captura = db.Column(db.String(10))
    motivo_cancelacion = db.Column(db.Text)
    # Sync / propagación
    sincronizado    = db.Column(db.Boolean, default=False)
    propagado_nacional = db.Column(db.Boolean, default=False)
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)

    comisaria_emisora = db.relationship('Comisaria', foreign_keys=[comisaria_emisora_id])
    emitido_por     = db.relationship('Usuario', foreign_keys=[emitido_por_id])

    @property
    def activo(self):
        if self.estado != 'activo':
            return False
        if self.fecha_expiracion and datetime.utcnow() > self.fecha_expiracion:
            return False
        return True


# ─────────────────────────────────────────────
# ALERTA DE PRÓFUGO (ALERTA LIGERA NACIONAL)
# ─────────────────────────────────────────────

class AlertaProfugo(db.Model):
    """
    Alerta ligera que se propaga a todas las provincias cuando
    se emite un warrant. Solo contiene datos mínimos para identificación.
    Equivalente a AlertaEpidemiologica en Bioko Health.
    """
    __tablename__ = 'alertas_profugo'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    warrant_uuid    = db.Column(db.String(36), nullable=False)
    sujeto_uuid     = db.Column(db.String(36), nullable=False)
    sujeto_dni      = db.Column(db.String(30))
    sujeto_nombres  = db.Column(db.String(100))
    sujeto_apellidos = db.Column(db.String(100))
    huella_hash     = db.Column(db.String(128))
    nivel_urgencia  = db.Column(db.String(20), default='normal')
    provincia_origen = db.Column(db.String(10))
    descripcion_breve = db.Column(db.String(500))
    activa          = db.Column(db.Boolean, default=True)
    creada_en       = db.Column(db.DateTime, default=datetime.utcnow)
    expira_en       = db.Column(db.DateTime)


# ─────────────────────────────────────────────
# REGISTRO DE SINCRONIZACIÓN
# ─────────────────────────────────────────────

class RegistroSync(db.Model):
    __tablename__ = 'registros_sync'
    id              = db.Column(db.Integer, primary_key=True)
    comisaria_origen = db.Column(db.String(30), nullable=False)
    tipo_dato       = db.Column(db.String(30), nullable=False)  # sujeto | detencion | warrant | alerta
    uuid_registro   = db.Column(db.String(36), nullable=False)
    accion          = db.Column(db.String(20), nullable=False)  # crear | actualizar | eliminar
    timestamp       = db.Column(db.DateTime, default=datetime.utcnow)
    estado          = db.Column(db.String(20), default='pendiente')  # pendiente | enviado | error
    intentos        = db.Column(db.Integer, default=0)
    error_mensaje   = db.Column(db.Text)


# ─────────────────────────────────────────────
# NODO RED
# ─────────────────────────────────────────────

class NodoComisaria(db.Model):
    __tablename__ = 'nodos_comisaria'
    id              = db.Column(db.Integer, primary_key=True)
    codigo          = db.Column(db.String(30), unique=True, nullable=False)
    nombre          = db.Column(db.String(150), nullable=False)
    tipo            = db.Column(db.String(30))
    ip_lan          = db.Column(db.String(45))
    puerto_lan      = db.Column(db.Integer, default=5000)
    lan_url         = db.Column(db.String(255))
    estado          = db.Column(db.String(20), default='activo')
    ultimo_contacto = db.Column(db.DateTime)
    version_app     = db.Column(db.String(20))

    @property
    def en_linea(self):
        if not self.ultimo_contacto:
            return False
        from datetime import timedelta
        return (datetime.utcnow() - self.ultimo_contacto).total_seconds() < 1800


# ─────────────────────────────────────────────
# SOLICITUD EXPEDIENTE INTER-PROVINCIAL
# ─────────────────────────────────────────────

class SolicitudExpediente(db.Model):
    """
    Solicitud del historial criminal de un sujeto que pertenece
    a otra provincia. Mismo flujo que en Bioko Health.
    """
    __tablename__ = 'solicitudes_expediente'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    comisaria_solicitante_codigo = db.Column(db.String(30), nullable=False)
    provincia_solicitante = db.Column(db.String(10), nullable=False)
    provincia_origen = db.Column(db.String(10), nullable=False)
    sujeto_uuid     = db.Column(db.String(36), nullable=False)
    sujeto_numero_expediente = db.Column(db.String(20))
    estado          = db.Column(db.String(20), default='pendiente')
    # pendiente → enviada → recibida → entregada → expirada
    motivo          = db.Column(db.Text)
    urgente         = db.Column(db.Boolean, default=False)
    creada_en       = db.Column(db.DateTime, default=datetime.utcnow)
    respondida_en   = db.Column(db.DateTime)
    expira_en       = db.Column(db.DateTime)
    solicitada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))


class CacheExpediente(db.Model):
    """Caché temporal de expedientes criminales de otras provincias."""
    __tablename__ = 'cache_expedientes'
    id              = db.Column(db.Integer, primary_key=True)
    solicitud_id    = db.Column(db.Integer, db.ForeignKey('solicitudes_expediente.id'))
    sujeto_uuid     = db.Column(db.String(36), nullable=False, index=True)
    provincia_origen = db.Column(db.String(10), nullable=False)
    datos_sujeto    = db.Column(db.Text, nullable=False)    # JSON
    datos_detenciones = db.Column(db.Text, nullable=False)  # JSON array
    datos_warrants  = db.Column(db.Text)                    # JSON array
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    expira_en       = db.Column(db.DateTime, nullable=False)
    activo          = db.Column(db.Boolean, default=True)

    @property
    def expirado(self):
        return datetime.utcnow() > self.expira_en


class TransferenciaDetenido(db.Model):
    """Transferencia formal de un detenido entre comisarías."""
    __tablename__ = 'transferencias_detenido'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)
    sujeto_id       = db.Column(db.Integer, db.ForeignKey('sujetos.id'), nullable=False)
    detencion_id    = db.Column(db.Integer, db.ForeignKey('detenciones.id'))
    comisaria_origen_codigo = db.Column(db.String(30), nullable=False)
    provincia_origen = db.Column(db.String(10), nullable=False)
    comisaria_destino_codigo = db.Column(db.String(30), nullable=False)
    provincia_destino = db.Column(db.String(10), nullable=False)
    motivo          = db.Column(db.Text, nullable=False)
    urgente         = db.Column(db.Boolean, default=False)
    estado          = db.Column(db.String(20), default='iniciada')
    # iniciada → en_transito → confirmada → completada → rechazada
    iniciada_en     = db.Column(db.DateTime, default=datetime.utcnow)
    confirmada_en   = db.Column(db.DateTime)
    completada_en   = db.Column(db.DateTime)
    notas           = db.Column(db.Text)
    iniciada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
