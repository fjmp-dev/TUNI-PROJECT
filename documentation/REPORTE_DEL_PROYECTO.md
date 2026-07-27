**MIR SUITE**

Reporte del Proyecto

Plataforma de manipulación móvil de doble brazo\
MiR200 · 2x UR5e · BrainCo Revo1 · Orbbec Gemini · Nordbo\
Universidad de Tampere (TUNI) / Fastlab

Preparado para el Prof. Lastra --- Versión 1.0, Julio 2026

# 1. Introducción

Este reporte resume el trabajo realizado durante los últimos dos meses en la plataforma robótica del Fastlab: una base móvil (el MiR200) que transporta dos brazos robóticos (UR5e), un par de manos robóticas, una cámara y sensores de fuerza. Explica, en términos sencillos, el estado en que se encontraba el sistema cuando empezamos, los problemas que enfrentamos y resolvimos en el camino, cómo está la situación ahora, y qué significa esto en la práctica para cualquiera que quiera usar el robot de aquí en adelante.

# 2. La Situación al Empezar

El robot ya era capaz de moverse y había sido programado por un miembro anterior del laboratorio, Eemil. Sin embargo, todo en él era frágil y difícil de usar:

- **Todo se operaba a mano.** Operar el robot significaba conectarse a su computadora interna mediante una terminal remota y escribir manualmente los comandos correctos, en el orden correcto, en la ventana de terminal correcta — algo que en realidad solo el autor original sabía hacer de forma confiable.
- **La base móvil sobrecargaba el sistema.** La base móvil (MiR200) enviaba constantemente una enorme cantidad de información interna de estado por el mismo canal de comunicación que usaban los brazos para hablar entre sí. Era el equivalente a que dos personas intentaran tener una conversación mientras otras cien voces hablaban por encima al mismo tiempo. El resultado era que la propia base móvil activaba su sistema de seguridad y se apagaba ("Error 9000"), y los brazos ocasionalmente perdían o retrasaban comandos.
- **No había ninguna red de seguridad.** Todo el software corría con acceso total y sin restricciones a la computadora interna, no había protección de contraseñas que valiera la pena mencionar, y no había forma de ver qué estaba haciendo el robot sin ser experto en las herramientas subyacentes.
- **No había forma de ver o controlar el robot remotamente.** Ninguna pantalla, ningún panel, nada — solo una línea de comandos.

En resumen: un robot que funcionaba, pero que solo una persona podía operar con seguridad, y en el que dos de sus propias partes principales (la base móvil y los brazos) interferían silenciosamente entre sí.

# 3. En Qué Trabajamos

## 3.1 Hacer el Software Modular y Seguro

Reorganizamos todo el software del robot en piezas claramente separadas y autocontenidas — una por cada parte física del robot (los brazos, la base móvil, la cámara, las manos) — usando una tecnología llamada Docker, que empaqueta cada pieza de software para que corra siempre de la misma manera y no pueda interferir accidentalmente con las demás. Junto con esto, quitamos el acceso irrestricto de "hacer cualquier cosa" que tenía cada una de estas piezas, y le dimos a cada una solo los permisos estrictamente necesarios para hacer su trabajo.

## 3.2 Detener la Sobrecarga que Causaba la Base Móvil

Encontramos y adoptamos una mejor forma (ya diseñada por otro miembro del equipo, Wael, para un proyecto relacionado) de conectar la base móvil con el resto del robot: en lugar de reenviar *todo* lo que dice la base móvil, ahora solo reenvía el puñado de cosas que realmente se necesitan (su posición, las lecturas de sus láseres de seguridad, el nivel de batería). La avalancha de información interna bajó aproximadamente un 95%, y el paro de emergencia autoinducido de la base móvil (el problema del "Error 9000") no ha vuelto a ocurrir desde entonces. También agregamos un vigilante automático que detecta si esta conexión alguna vez se congela y la reinicia por sí solo, sin que nadie tenga que notarlo o intervenir.

## 3.3 Construir un Panel de Control Real

Antes de este trabajo, no existía ninguna interfaz — solo una línea de comandos. Construimos un panel de control web propiamente dicho: iniciar sesión desde un navegador, ver el estado del robot en vivo, observar la transmisión de la cámara, mover los brazos, revisar la posición y batería de la base móvil, y encender o apagar distintas partes del sistema, todo desde una sola pantalla. También admite múltiples cuentas de usuario con distintos niveles de permiso, y cada conexión va cifrada, de modo que la información que viaja entre una laptop y el robot no puede ser leída por nadie más en la red. Las contraseñas por defecto se reemplazaron por contraseñas fuertes, y el acceso remoto a la terminal de la computadora interna (antes completamente abierto) ahora está cerrado y requiere su propia contraseña independiente.

## 3.4 Hacer los Brazos Confiables

Durante un tiempo, los brazos tuvieron un problema sutil y frustrante: el panel de control decía que un movimiento se había completado, pero el brazo en realidad no se movía. Rastreamos esto hasta el propio sistema de seguridad del robot, que detenía silenciosamente el programa de control del brazo en segundo plano (provocado por un ajuste de límite de velocidad en el robot que actualmente está configurado de forma demasiado conservadora) sin reportarlo con claridad. Corregimos el software para que ahora verifique que el brazo realmente se movió antes de reportar éxito, y reinicie automáticamente el programa de control del brazo cuando sea necesario. También agregamos un pequeño modelo 3D en pantalla de ambos brazos para poder revisar su posición de un vistazo, y una regla de seguridad que impide que una persona guíe un brazo con la mano hasta que el robot haya confirmado que efectivamente está sosteniendo algo (más de 1 kg), para que el brazo no se pueda mover a mano de forma inesperada.

## 3.5 Arreglar la Cámara

La transmisión de video en vivo de la cámara del robot era originalmente casi inutilizable — apenas uno o dos cuadros por segundo, más una presentación de diapositivas que un video. Encontramos que esto lo causaba la forma en que se convertían los datos de imagen para el navegador, no la cámara en sí, y tras ajustar la configuración de video la llevamos a unos fluidos ~30 cuadros por segundo.

## 3.6 Hacerlo Fácil de Usar para Cualquiera

Más recientemente, agregamos un ícono de escritorio sencillo: un clic enciende todo el sistema (y abre el panel de control automáticamente en el navegador), otro clic lo apaga. Sin comandos que recordar, sin necesidad de terminal. Encender los brazos en sí mismos sigue siendo un paso separado y deliberado que se toma desde dentro del panel de control, para que nada se mueva solo porque alguien encendió el sistema.

# 4. Problemas que Enfrentamos y Resolvimos

| Problema | Qué Estaba Pasando en Realidad | Cómo lo Corregimos |
|---|---|---|
| La base móvil se apagaba sola por un error de seguridad | Estaba inundando el canal de comunicación compartido con muchísima más información de la que nadie necesitaba | Cambiamos a reenviar solo el puñado de piezas de información esenciales |
| El "vigilante de seguridad" que construimos reiniciaba por sí mismo una conexión perfectamente sana | Estaba revisando actividad en el lugar equivocado, así que siempre parecía inactiva aunque no lo estuviera | Lo reescribimos para que revise datos reales y en vivo |
| Los movimientos de los brazos fallaban en silencio — el panel decía "listo" pero nada se movía | El sistema de seguridad del robot había pausado silenciosamente el programa de control del brazo | Hicimos que el software verifique que el brazo realmente se movió, y reinicie automáticamente el programa de control |
| Editar un archivo de configuración en la computadora a veces no tenía ningún efecto en el sistema en ejecución | Una particularidad de cómo Docker mantiene separados los archivos de un programa en ejecución de los del disco | Aprendimos a aplicar la corrección directamente dentro del programa en ejecución |
| La transmisión de cámara en vivo era extremadamente lenta | La forma en que se codificaban los cuadros de video para el navegador sobrecargaba la computadora interna | Bajamos la resolución de video a un ajuste que la cámara soporta completamente a velocidad máxima |
| La base móvil perdía la conexión constantemente | Una señal WiFi débil en la banda de red que estaba usando | Diagnosticamos la causa exacta e identificamos la corrección (moverla a otra banda WiFi con mejor alcance); esto ya se corrigió una vez y necesita volver a aplicarse tras un cambio reciente de red |
| Una herramienta de grabación llenó todo el disco duro en pocas horas | Estaba guardando muchísimos más datos de los previstos, sin ningún límite | Limitamos qué y cuánto tiempo graba |
| Los datos de los sensores parecían "estar ahí" pero en realidad estaban vacíos tras reiniciar partes del sistema | Un residuo técnico de cómo el sistema de comunicación comparte memoria entre programas | Documentamos la causa y el paso sencillo de limpieza |
| La base móvil ocasionalmente se detenía sola, culpando a un obstáculo que no estaba realmente ahí | Una interrupción real (aunque breve) de su sensor de seguridad trasero, muy probablemente un cable suelto o una ventana del sensor sucia | Diagnosticamos el patrón; una inspección física es el paso que falta |
| Contraseñas débiles, por defecto o compartidas por todas partes | El sistema nunca se configuró pensando en seguridad | Reemplazamos todas las contraseñas por defecto, ciframos cómo se almacenan, y cerramos el acceso remoto a la terminal |

# 5. Cómo Está el Proyecto Ahora

- La base móvil y los brazos ya no interfieren entre sí, y los apagones autoinducidos de la base móvil se detuvieron.
- Cada parte del sistema corre solo con el acceso que realmente necesita, en lugar de control total y sin restricciones de la computadora.
- Toda la comunicación con el robot está cifrada y requiere iniciar sesión.
- Existe un panel de control real y funcional: estado en vivo, vista de cámara, control de brazos con vista previa 3D, y gestión del sistema, usable por varias personas con distintos niveles de permiso.
- La cámara transmite de forma fluida en tiempo real.
- Encender o apagar todo el sistema toma un clic.
- Cuando algo sale mal, el sistema ahora lo dice con claridad, en lugar de fallar en silencio.
- Los pendientes que quedan son conocidos, están documentados y asignados — no son fallas intermitentes sin explicación.

# 6. Cómo Ayudamos al Desarrollo del Robot

En pocas palabras, el robot pasó de ser un sistema que solo su constructor original podía operar con seguridad, a uno que razonablemente se le puede entregar a alguien más. La base móvil y los brazos ahora se pueden usar juntos sin que uno rompa al otro — algo que importa muchísimo para un robot cuyo propósito completo es moverse *y* manipular objetos al mismo tiempo. Cualquiera en el laboratorio puede ahora revisar el robot, mover un brazo, u observar la cámara desde un navegador, sin necesitar conocer los detalles técnicos internos ni tener acceso a la terminal. Problemas que antes eran invisibles (un movimiento fallido en silencio, una conexión congelada) ahora salen a la luz de inmediato y muchas veces se resuelven solos. Y como la seguridad básica ya está en su lugar, el sistema está en un estado razonable para mostrarse a visitantes, o eventualmente hacerse accesible desde fuera del laboratorio — ninguna de las dos cosas era realista antes.

# 7. Antes vs. Ahora

**Antes**, usar el robot significaba: conectarse a su computadora interna mediante una terminal remota, conocer los comandos técnicos exactos y el orden en que había que ejecutarlos, esperar que la base móvil no activara su propio paro de emergencia, y no tener forma de ver la cámara o el estado del robot sin herramientas especializadas — sin inicio de sesión, sin cifrado, y sin registro de quién hizo qué.

**Ahora**, usar el robot significa: hacer clic en un ícono del escritorio (o abrir una sola dirección web) para encender el sistema, iniciar sesión con una cuenta personal, y desde una sola pantalla: encender la parte del robot que se necesite, mover los brazos y observar una vista previa 3D de su posición, guiar el robot a mano de forma segura, ver la cámara en vivo y el estado de la base móvil, y — si alguna vez hace falta una corrección técnica — abrir una terminal integrada en lugar de una conexión remota aparte. Todo esto ahora ocurre sobre una conexión cifrada y con sesión iniciada, y el parloteo interno de la base móvil ya no inunda el sistema del que dependen los brazos.

# 8. Pendientes

- **Ajuste del límite de velocidad de los brazos**: actualmente lo bastante conservador como para pausar movimientos normales de vez en cuando; necesita ajustarse directamente en el robot (requiere a Wael).
- **WiFi de la base móvil**: actualmente en una señal débil; necesita moverse de vuelta a la banda de red de mejor rendimiento (requiere a Wael / al equipo de red).
- **Acceso remoto desde fuera del laboratorio**: técnicamente posible, pero requiere un pequeño cambio en el plan de datos celular más el mismo endurecimiento de seguridad ya aplicado en el resto del sistema; el plan ya está acordado, falta ejecutarlo.
- **Reloj interno de la base móvil**: desfasado por unos diez años (cosmético — solo afecta las marcas de tiempo de los registros).
- **Fases futuras**: el sistema de batería de las manos robóticas y un cuello motorizado están documentados pero aún no integrados; una capacidad completa de autonavegación para la base móvil está planeada como la siguiente fase mayor.
