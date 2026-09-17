# Calendario laboral de México

El calendario se mantiene **por empresa**. Esto permite que el grupo comparta
personas, pero cada razón social conserve sus propios días internos y reglas
operativas.

## Días legales generados

La generación idempotente agrega los días previsibles del artículo 74 de la
Ley Federal del Trabajo: 1 de enero; primer lunes de febrero; tercer lunes de
marzo; 1 de mayo; 16 de septiembre; tercer lunes de noviembre; 25 de
diciembre; y el 1 de octubre cada seis años cuando corresponda a la
transmisión del Poder Ejecutivo Federal. La reforma que cambió la fecha a 1 de
octubre se publicó el 30 de septiembre de 2024. La jornada electoral no se
puede inferir y debe capturarse como día de tipo `electoral`.

La fuente normativa debe revisarse en cada actualización legal:
[artículo 74 vigente de la LFT (SCJN)](https://legislacion.scjn.gob.mx/consulta/articulo?idArt=302971&idOrd=410&idRef=57),
[decreto DOF 2024](https://sidof.segob.gob.mx/notas/docFuente/5739950).

## Operación

- La tarea `adms.ensure_statutory_holidays` corre diariamente a las 02:10 y
  asegura el año actual y el siguiente para todas las empresas activas.
- Es segura de repetir: conserva cualquier fecha capturada por RRHH y sólo
  crea días legales faltantes.
- En la pantalla **Feriados**, el botón **Generar o reparar legales** ejecuta
  la misma operación de manera inmediata para una empresa y año.
- Los días de aniversario, cierres internos y las elecciones se agregan
  manualmente y permanecen separados de la fuente legal.

Para desplegar la automatización con Celery se requieren un worker y un beat:

```sh
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
celery -A app.workers.celery_app:celery_app beat --loglevel=INFO
```

## Datos personales protegidos

CURP, RFC y NSS/IMSS no van en la tabla principal de personas. Se cifran con
Fernet antes de persistirse. Configure una clave única fuera de Git:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarde el resultado en el secreto `ZKTECO_HR_PII_ENCRYPTION_KEY` y mantenga
controles de acceso y rotación propios de producción.
