# Consulta de usuarios y enrolamiento del SpeedFace V5L

Revisión: 1 de octubre de 2026.

## Modelo y versiones

El usuario indica que el firmware actual es superior a 3. El archivo histórico
local `SOPORTE.md` contiene `DeviceType=acc`,
`FirmVer=ZAM230-NF50VA-Ver1.1.9` y `PushVersion=Ver 3.1.6S-20251028`.
Ese registro no es una lectura actual del reloj. Deben conservarse por
separado el firmware y la versión PUSH que reporte hoy el equipo.

[La página oficial del V5L](https://www.zkteco.com/en/SpeedFaceSeries/SpeedFace-V5L-Series)
incluye documentación de la plataforma ZAM230 y distingue AC PUSH de TA PUSH.
Ofrece el manual ZAM230 fechado 2025-09-09, con descarga mediante cuenta.
La búsqueda no encontró una especificación pública específica del build
`3.1.6S-20251028` ni una matriz de comandos para el firmware actual.

## Diagnóstico del código

La implementación anterior tenía cinco problemas comprobables:

1. Enviaba `DATA QUERY USERINFO` también a dispositivos `DeviceType=acc`.
2. En `querydata`, daba prioridad a `type=tabledata` e ignoraba
   `tablename=user`, descartando el inventario como una tabla desconocida.
3. Respondía `OK` a esos datos de usuarios.
4. El parser no reconocía `CardNo` ni el prefijo `user ` cuando precedía a PIN.
5. Trataba cualquier retorno positivo como fallo, aunque una consulta AC
   pueda devolver el número de filas.

Además, las subidas `cdata?table=tabledata&tablename=user` pasaban por el
procesador de información del dispositivo, sin crear usuarios del reloj.

El [manual Security PUSH de ZKTeco, marzo de 2020](https://www.scribd.com/document/604031919/Security-PUSH-Communication-Protocol-20200325-002)
documenta `-629` como nombre de tabla incorrecto, la consulta
`DATA QUERY tablename=user,fielddesc=*,filter=*`, el retorno mediante
`querydata` y el acuse `user=N` (§10.5 y consulta de usuarios, pp. 127–128;
apéndice 1). Su versión de protocolo es 3.1.2, y su versión documental es
1.5: ninguna de ellas identifica el firmware actual del usuario.

Si el retorno crudo es **`Return=-629`**, la mezcla de dialectos es una
explicación consistente con la documentación y el código. Un número `629`
mostrado sin signo todavía requiere revisar el cuerpo de `devicecmd`.
Este diagnóstico no demuestra que al reloj le falte la consulta.

## Corrección y validación

El constructor selecciona el dialecto por `DeviceType`. La recepción procesa
la tabla `user` en ambas rutas, importa cada página sin duplicar PIN y acusa
su cantidad. Reconoce tarjetas y conserva el enmascaramiento de contraseñas.
Los retornos no negativos se aceptan para la consulta AC documentada.

También se corrigieron los nombres de tabla y campos de alta, edición y baja
AC en los constructores que usa el modo de laboratorio. Su bloqueo habitual
sigue vigente hasta contar con evidencia del equipo.

Las pruebas de servidor ejercitan el formato documentado; no prueban que el
firmware actual lo implemente. Para validar el reloj, desplegar la corrección
y ejecutar **Personal en reloj → Consultar usuarios del reloj** una vez.
Correlacionar el comando, `querydata`, su acuse y `devicecmd` por ID; guardar
los valores actuales de firmware y PUSH junto con la captura.

## Enrolamiento

`update_enrollment_request` sólo cambia estados administrativos. No encola
una orden de captura biométrica. El botón anterior «Enviar a enrolar» podía
hacer pensar que había una comunicación con el reloj; ahora indica
«Enrolar en reloj» y explica la captura presencial.

La recepción corregida permite importar la identidad que el terminal suba
tras el alta presencial. Iniciar la captura desde la aplicación requiere
otra integración: comando, capacidades y eventos de finalización específicos
del firmware actual. Esta búsqueda no confirmó ese contrato para su build.
La ausencia de esa integración en el código no demuestra que el modelo
carezca de enrolamiento remoto.

## Verificación local

- 76 pruebas seleccionadas de protocolo y ciclo de vida pasaron, con
  PostgreSQL 16 y Redis 7 aislados. Incluyen páginas repetidas, inventario
  vacío, retorno positivo, `-629`, subidas presenciales y escrituras de
  laboratorio.
- Mypy pasó sobre los 73 archivos de aplicación.
- TypeScript y ESLint del frontend pasaron.
- Ruff y formato pasaron para los archivos Python modificados. El lint
  global conserva tres errores E501 previos en `backend/app/api/v1/hr.py`,
  que no se modificó en esta revisión.
- No se enviaron comandos al reloj ni se validó su firmware actual.
