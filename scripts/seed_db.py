"""
SRCN — Seed inicial de base de datos
Ejecutar: flask --app run seed-db
O: python scripts/seed_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.models import db, Usuario, Comisaria, Provincia, Distrito, CategoriaDelito


def seed():
    app = create_app('development')
    with app.app_context():
        db.create_all()

        # Provincias
        provincias = [
            ('BN', 'Bioko Norte', 'Malabo', True),
            ('BS', 'Bioko Sur', 'Luba', True),
            ('LIT', 'Litoral', 'Bata', False),
            ('CS', 'Centro Sur', 'Evinayong', False),
            ('KN', 'Kié-Ntem', 'Ebebiyín', False),
            ('WN', 'Wele-Nzas', 'Mongomo', False),
            ('ANB', 'Annobón', 'San Antonio de Palé', True),
        ]
        for codigo, nombre, sede, isla in provincias:
            if not Provincia.query.filter_by(codigo=codigo).first():
                db.session.add(Provincia(codigo=codigo, nombre=nombre, sede=sede))

        db.session.flush()

        # Comisaría local
        prov_bn = Provincia.query.filter_by(codigo='BN').first()
        if not Comisaria.query.filter_by(codigo='COM-BN-001').first():
            db.session.add(Comisaria(
                codigo='COM-BN-001',
                nombre='Comisaría Central Malabo',
                tipo='comisaria',
                provincia_id=prov_bn.id if prov_bn else None,
                activa=True,
                es_nodo_local=True,
            ))
        db.session.flush()
        comisaria = Comisaria.query.filter_by(codigo='COM-BN-001').first()

        # Categorías de delito
        delitos = [
            ('DL-001', 'Robo', 'contra_propiedad', 'delito_menor'),
            ('DL-002', 'Robo con violencia', 'contra_propiedad', 'delito_grave'),
            ('DL-003', 'Tráfico de estupefacientes', 'narco', 'delito_grave'),
            ('DL-004', 'Tráfico internacional de narcóticos', 'narco', 'crimen'),
            ('DL-005', 'Agresión', 'contra_personas', 'delito_menor'),
            ('DL-006', 'Agresión grave', 'contra_personas', 'delito_grave'),
            ('DL-007', 'Homicidio', 'contra_personas', 'crimen'),
            ('DL-008', 'Fraude y estafa', 'economico', 'delito_menor'),
            ('DL-009', 'Alteración del orden público', 'orden_publico', 'falta'),
            ('DL-010', 'Tenencia ilícita de armas', 'orden_publico', 'delito_grave'),
        ]
        for codigo, nombre, categoria, gravedad in delitos:
            if not CategoriaDelito.query.filter_by(codigo=codigo).first():
                db.session.add(CategoriaDelito(
                    codigo=codigo, nombre=nombre,
                    categoria=categoria, gravedad=gravedad, activa=True
                ))

        # Admin user
        if not Usuario.query.filter_by(nombre_usuario='admin').first():
            admin = Usuario(
                nombre_usuario='admin',
                nombre_completo='Administrador SRCN',
                rol='superadmin',
                comisaria_id=comisaria.id if comisaria else None,
            )
            admin.set_password('srcn_admin_2026')
            db.session.add(admin)
            print("Admin creado: admin / srcn_admin_2026")

        # Demo agent
        if not Usuario.query.filter_by(nombre_usuario='agente01').first():
            agente = Usuario(
                nombre_usuario='agente01',
                nombre_completo='Agente Ejemplo Nsue',
                rol='agente',
                numero_placa='AGT-BN-001',
                comisaria_id=comisaria.id if comisaria else None,
            )
            agente.set_password('agente_2026')
            db.session.add(agente)
            print("Agente creado: agente01 / agente_2026")

        db.session.commit()
        print("Seed completado correctamente.")

if __name__ == '__main__':
    seed()
