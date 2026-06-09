# SRCN — Servidor Central — Ministerio del Interior

Nodo de Nivel 3. Único servidor nacional. MySQL, índice nacional de sujetos y warrants, motor de alertas.

## Sistema de Registro Criminal Nacional — Guinea Ecuatorial

**Ministerio de Seguridad Nacional / Ministerio del Interior**

---

## Arquitectura

El SRCN opera en 3 niveles:

```
Nivel 1: Comisarías      → SQLite + Flask    (nodo local por estación)
Nivel 2: Nodos Provinciales → MySQL + Flask  (un nodo por provincia)
Nivel 3: Servidor Central   → MySQL + Flask  (Ministerio, Malabo)
```

Este repositorio corresponde al **Servidor Central — Ministerio del Interior**.

## Instalación rápida

```bash
cp .env.template .env
# Editar .env con los valores de esta instalación
bash deploy/instalar.sh
```

## Roles de usuario

| Rol | Permisos |
|-----|----------|
| superadmin | Acceso total |
| jefe | Emitir warrants, ver toda la comisaría |
| inspector | Emitir warrants, gestionar expedientes |
| agente | Registrar detenciones, consultar antecedentes |
| readonly | Solo lectura |

## Seguridad

- Toda comunicación entre nodos usa tokens HMAC ()
- Inter-provincial: mTLS con certificados por provincia
- Audit log inmutable: todas las consultas quedan registradas
- Sin acceso público a internet desde las comisarías

## Datos de contacto técnico

Sistema desarrollado por **BP Technology** para el Ministerio del Interior de Guinea Ecuatorial.
