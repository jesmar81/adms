# Guía de uso

Manual para las personas que administran relojes, personal y asistencia desde
la interfaz web de ZKTeco ADMS. La disponibilidad de cada pantalla depende de
los permisos y del alcance de empresa/grupo asignados a la cuenta.

## 1. Entrar al sistema

1. Abre la dirección web entregada por quien opera la instalación. En un
   entorno Docker local suele ser `http://localhost:3000`.
2. Inicia sesión con tu nombre de usuario y contraseña.
3. Usa el menú lateral para abrir un módulo. En una pantalla pequeña, abre el
   menú con el botón correspondiente.
4. Para terminar, abre el menú de usuario y selecciona cerrar sesión.

Los tokens de sesión se mantienen en memoria del navegador. Al recargar la
página es normal que se solicite iniciar sesión de nuevo. No compartas tu
contraseña ni dejes una sesión abierta en un equipo compartido.

## 2. Conceptos de trabajo

- **Grupo corporativo**: agrupa una o más razones sociales.
- **Empresa**: entidad legal que concentra personal, horarios, feriados y
  reportes.
- **Sucursal**: ubicación de trabajo asociada a una empresa.
- **Persona**: expediente de identidad. Sus datos personales no son por sí
  solos un empleo.
- **Empleo**: relación de una persona con una empresa, con número, puesto,
  fechas, estado y condiciones laborales. Los reportes de asistencia se
  calculan sobre empleos.
- **Reloj**: terminal físico autorizado por número de serie.
- **Usuario del reloj**: PIN y nombre enviados o recibidos por un terminal.
  No es la cuenta que inicia sesión en esta web.
- **Marcación**: evento original recibido del reloj. Los ajustes de RR. HH. se
  guardan aparte y no reescriben ese evento original.

## 3. Orden recomendado para la configuración inicial

1. Crear el grupo corporativo, las empresas y las sucursales.
2. Crear las cuentas del equipo y asignar roles y alcances adecuados.
3. Crear personas y su empleo vigente en la empresa correspondiente.
4. Crear los horarios, asignarlos a los empleos y revisar los días de
   descanso.
5. Crear o reparar los feriados de cada empresa y agregar los días internos
   necesarios.
6. Autorizar cada reloj por número de serie; después configurar su conexión
   ADMS y comprobar que se comunique.
7. Vincular PIN de reloj con personas y, cuando corresponda, tramitar los
   enrolamientos.
8. Revisar las marcaciones y reportes de un periodo conocido antes de usarlos
   en procesos operativos.

La configuración previa afecta los cálculos: sin empleo, horario y zona
horaria correctos pueden faltar personas en reportes o calcularse mal la
puntualidad.

## 4. Módulos

### Centro de control

Presenta un resumen operativo de los dispositivos, actividad y asistencia
disponible para tu alcance. Úsalo como punto de entrada; para investigar un
registro abre el módulo específico. La información depende de los datos que
hayan llegado a la plataforma y no sustituye la revisión del reloj.

### Relojes

Lista los terminales autorizados, sus datos operativos y actividad observada.
Para dar de alta uno:

1. Selecciona **Agregar reloj**.
2. Escribe el número de serie (1–64 caracteres: letras, números, guion o guion
   bajo), un nombre operativo y el modelo.
3. Selecciona una sucursal si aplica y confirma la zona horaria.
4. Pulsa **Autorizar reloj**.
5. Configura en el terminal el servidor ADMS que muestra la ventana. En
   Docker local suele ser `http://localhost:8000`; desde un reloj físico,
   `localhost` significa el propio reloj, así que debes usar una dirección IP
   o nombre DNS alcanzable desde el equipo.
6. Comprueba que aparezca actividad reciente después de que el reloj se
   conecte.

Solo se admiten seriales previamente autorizados por defecto. Registrar el
serial en la aplicación no configura por sí mismo el terminal ni prueba su
conectividad. Consulta [Alta y conexión de un reloj](OPERACION_Y_DESPLIEGUE.md#alta-y-conexion-de-un-reloj).

### Comandos

Permite revisar y encolar operaciones que el sistema expone para un reloj. Elige
el reloj, selecciona una acción disponible y confirma los parámetros
permitidos. Una orden encolada no implica que se haya ejecutado: revisa el
estado, los intentos y la confirmación devuelta por el equipo. Las acciones
disponibles dependen del perfil de capacidad y firmware. No se admite texto de
comando libre.

### Empresas y sucursales

1. Crea el grupo corporativo.
2. Dentro del grupo agrega cada empresa con razón social y los datos legales
   disponibles.
3. Agrega sucursales con su nombre, clave y dirección.
4. Mantén la empresa activa mientras tenga relaciones o historial que deban
   consultarse.

Las desactivaciones son preferibles a borrar datos históricos. Las operaciones
de borrado, cuando estén disponibles, pueden tener validaciones adicionales y
afectar relaciones.

### Trabajadores

Usa **Trabajadores** para buscar personas y abrir su expediente. Al crear una
persona, captura nombre y apellidos requeridos, grupo y los datos de contacto
necesarios. Después completa en el expediente el empleo asociado a la empresa,
su número de empleado, puesto, fechas y demás información laboral.

La fotografía admite JPG, PNG o WebP hasta 5 MB. CURP, RFC, NSS y datos fiscales
son información sensible: solo deben capturarse si la operación lo requiere y
tu rol tiene permiso. El acceso a esos datos se controla y audita.

Una persona puede tener varios empleos, incluso en distintas empresas del
mismo grupo. Confirma que el empleo correcto esté activo antes de asignar
horarios, relacionar marcas o consultar una tarjeta semanal.

### Horarios

1. Selecciona la empresa y crea un horario con nombre y zona horaria.
2. Define hora de entrada y salida, tolerancia, periodos de comida y días de
   descanso según la operación.
3. Asigna el horario al empleo correspondiente e indica su vigencia.
4. Revisa el efecto en los reportes de un periodo de prueba.

Los cambios de horario conservan versiones para proteger el historial. Cambiar
el catálogo no necesariamente reescribe asignaciones históricas; registra una
nueva vigencia cuando cambien las condiciones de una persona.

### Feriados

Selecciona empresa y año. **Generar o reparar legales** agrega las fechas
previsibles de descanso obligatorio configuradas por la aplicación y puede
repetirse sin duplicar fechas. Agrega manualmente días internos y jornadas
electorales cuando correspondan. Verifica cada año el calendario y la
normativa aplicable; la generación no conoce cierres locales ni fechas
electorales por adelantado. Más información: [Calendario laboral de México](HR_CALENDARS_MX.md).

### Personal en reloj

Consulta los usuarios reportados o administrados por terminal. Selecciona el
reloj e identifica el PIN. Puedes vincularlo con una persona cuando tengas
certeza de que corresponde al mismo trabajador. Los registros pueden mostrarse
como pendientes hasta que el reloj confirme la sincronización. Una asociación
en la aplicación no crea por sí sola un usuario físico si no se envió y
confirmó una operación compatible.

### Enrolamientos

Este módulo lleva el flujo administrativo de solicitud y seguimiento de un
enrolamiento (rostro, huella, palma o tarjeta según opciones disponibles):

1. Inicia una solicitud para el reloj y trabajador/empleo correspondiente.
2. Elige el método y, para huella, las posiciones requeridas.
3. Completa la verificación de identidad con una referencia operativa, por
   ejemplo “INE cotejada”, y revisa los datos asociados.
4. Aprueba la solicitud y avanza el estado según la pantalla.
5. Completa la captura siguiendo las instrucciones del terminal y confirma el
   resultado registrado.

Un mismo usuario de RR. HH. autorizado puede registrar la solicitud, verificar
la identidad y aprobarla; no se exige una segunda cuenta para el mismo
enrolamiento. La aplicación no necesita guardar una copia del consentimiento
biométrico para este flujo. La captura biométrica ocurre en el equipo cuando
ese modelo y operación lo permiten; no asumas que la plantilla biométrica se
sincroniza o se almacena en esta aplicación. Si el terminal no confirma la
acción, revisa compatibilidad y conexión.

### Marcaciones

Busca eventos usando filtros como reloj, PIN, rango de fechas, estado, método
de verificación o código de trabajo. Revisa la atribución de cada registro:
asignado, ambiguo o sin asignar. Si tienes permiso para escribir asistencia,
puedes resolver una atribución seleccionando el empleo correcto y dejando un
motivo. La marca original recibida se conserva.

Si una checada no aparece, comprueba la conexión del dispositivo, el PIN, el
rango de fechas, el estado y la asignación del usuario del reloj. La pantalla
solo puede mostrar información recibida y persistida por la API.

### Llegadas en vivo

Selecciona la empresa para ver a quién se esperaba según el horario vigente y
quién aún no ha registrado una entrada. La lista se actualiza automáticamente
y una persona deja de aparecer cuando llega la marca. Requiere empleos activos,
horarios y zona horaria correctos; no trata descansos ni días no laborables
como entradas pendientes.

### Reportes y tiempo extra

En **Reportes**, selecciona empresa/persona y periodo según el reporte, y pulsa
la acción para consultar:

| Reporte | Uso |
|---|---|
| Pendientes de entrada en vivo | Personas que ya debían entrar y aún no registran una checada. |
| Llegadas del día | Primera checada y número de marcas por trabajador para una fecha. |
| Faltas | Días laborales sin asistencia; descansos y feriados se excluyen según configuración. |
| Tarjeta semanal | Vista de lunes a domingo con comidas, incidencias y ajustes de RR. HH. |
| Puntualidad histórica | Retardos y salidas anticipadas en un rango de fechas. |
| Tiempo extra | Detección y flujo de revisión de RR. HH. y autorización de Dirección. |

Las tarjetas semanales se pueden exportar a PDF por trabajador, empresa o
grupo cuando tu rol y los filtros lo permitan. Los ajustes de tarjeta requieren
un motivo y no alteran las marcaciones originales del reloj. Revisa el horario,
feriados y zona horaria antes de concluir que un resultado es una falta o
retardo.

### Usuarios y permisos

Un administrador crea cuentas con usuario, correo y contraseña de al menos 15
caracteres, asigna un rol y limita el alcance a grupos o empresas cuando
corresponda. Los roles estándar incluyen administrador, RR. HH., operador,
consulta y dirección, con permisos distintos. Una cuenta con alcance de empresa
no obtiene acceso a empresas hermanas del mismo grupo.

Asigna el menor permiso necesario. El menú solo muestra módulos para los que
la cuenta tiene permiso, pero la API vuelve a comprobar permisos y alcance. La
acción de desactivar impide el acceso sin borrar el historial asociado. La
cuenta de superusuario es privilegiada y debe reservarse para administración.

### Auditoría

Permite consultar eventos administrativos registrados, como accesos y cambios
relevantes. Es una vista de consulta; sirve para rastrear acciones y no para
editar el historial.

## 5. Buenas prácticas

- Mantén empresa, empleo, horario, sucursal, zona horaria y PIN consistentes.
- Revisa una muestra de registros después de cambios de catálogo o de
  conectividad.
- Deja motivos claros en ajustes y correcciones.
- No uses datos reales en una instancia de prueba sin autorización y controles
  adecuados.
- Evita recopilar identificadores sensibles que no sean necesarios.
- Considera el estado “pendiente” como falta de confirmación, no como éxito.
- Para problemas de acceso, solicita a un administrador que revise rol y
  alcance; no compartas credenciales.

## 6. Solución rápida de problemas

| Síntoma | Comprobaciones |
|---|---|
| No puedo entrar | URL, usuario activo, contraseña, conexión a API y Redis del servicio. Solicita restablecimiento al administrador. |
| No veo una sección o empresa | Permiso del rol y alcance de grupo/empresa. |
| El reloj no aparece en línea | Serial autorizado, URL ADMS alcanzable desde el reloj, puerto/firewall, fecha/hora y logs del backend. |
| No llegan marcaciones | Estado de conexión, tabla/evento enviado por firmware, rango de fechas y logs ADMS. |
| PIN sin persona | Vincula el usuario del reloj con el empleo/persona correctos. |
| Reporte vacío o inesperado | Empleo activo, asignación y vigencia de horario, feriado, empresa, fechas y zona horaria. |
| Orden de reloj pendiente | Revisa disponibilidad del terminal, perfil de capacidad, confirmación y errores. No repitas órdenes indiscriminadamente. |
| Enrolamiento no concluye | Estado del flujo, conectividad y compatibilidad de la función con firmware. Completar la etapa web no demuestra captura física. |

Para operaciones de infraestructura, sigue [Instalación y operación](OPERACION_Y_DESPLIEGUE.md#solucion-de-problemas) y conserva fecha, serial, request ID y mensajes relevantes sin compartir contraseñas, tokens ni plantillas biométricas.
