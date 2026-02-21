# Especificaciones del proyecto

## Objetivo

El objetivo es crear una aplicacion para la gestión de la tensión arterial, necesito un dashboard como página principal que refleje las ultimas mediciones y graficas de seguimiento.

Y una segunda pantalla que muestre los datos de la tensión arterial en función de los datos de los complejos vitaminicos y complementos, así como las observaciones y si se puede establecer un patrón en funcion de las actividades realizadas, el estado de ánimo, el tipo de comida y el tipo de actividad física (generalmente asisto a dos gimnasios, uno de fuerza y cardio por las mañanas y otro de karate por las tardes.)

El control de la tensión se divide en dos escenarios, el primero es una medición intensa en la que e realizan dos medidas de tensión durante el dia, una por la mañana y otra por la noche.

El otro escenario, es el de medidas de control, que se realizaran de vez en cuando (mañana o tarde), el sistema de medición es el mismo, 3 medidas y calculo de la media. 

Ambos escenarios tendrá páginas de seguimiento separadas, una para la medición intensa y otra para la medición de control.

## Procedimiento

cada medición consta de 3 pruebas que se realizarán consecutivas y el valor a tener en cuenta para mostrar en una gráfica de velas sera la media de las tres medidas, los valores tomados, sera la presión sistólica, la presión diastólica y las pulsaciones.

Otros datos a tener en cuenta:

- Toma de suplementos y complejos vitaminicos (Espirulina, fibra, perlas de ajo, etc)
- Si la medida es por la mañana o por la noche
- Si la medida es de control o de medición intensa
- Estado de ánimo
- Tipo de comida
- Tipo de actividad física
- Observaciones

Con todos estos datos se puede estudiar un patron de variabilidad de la tensión en función de esos datos. 

## Interfaz

La interfaz sera una página principal que refleje las ultimas mediciones y graficas de seguimiento. Esta tiene un mockup realizado con Stitch que se llama "Hipertension Analitics ¬ Logging" que se encuentra en el siguiente enlace: https://stitch.withgoogle.com/projects/14595689369559055727?pli=1

El dashboard deberá tener variaciones a fin de incorporar todos los datos necesarios para el estudio de la variabilidad de la tensión arterial. 

Las medidas apareceran separadas, en un grupo las medidas realizadas y en otro, el resultado de calcular la media. 

La gráfica principal, sera una gráfica de velas, donde la vela es el valor entre el dato de la tensión sistólica y la diastólica, y será el valor calculado de la media. 

Tambien habrá otro gráfico donde se pueda ver la evolución de cada tensión (systólica, diastólica) a través del tiempo, del tipo gráfica de lineas). 

Debe tener un formulario para la introducción de los datos de cada medición, con la fecha y si es medición de mañana o de noche. Tambien debe tener datos adjuntos al dia que son la toma de complejos vitaminicos y complementos, así como observaciones.

## Stack tecnológico

- Frontend: Bootstrap, HTML, CSS, JavaScript
- Backend: Django
- Librerias de gráficos: Chart.js
- Base de datos: SQLite

## Seguridad

- La aplicacion debe tener una autenticacion de usuario y contraseña
- La aplicacion debe tener una sesion de usuario y contraseña
- El usuario se debe autenticar usando su correo electrónico, para lo que habrá que extender el modelo de usuario de django para que tenga un correo electronico y una contraseña.
- Se deberar primar la seguridad de el sitio controlando en los formularios la entrada  de datos, para lo que se debera validar que los datos introducidos sean correctos y que no se introduzcan datos no validos.
- Se debera implementar un sistema de autenticacion que permita al usuario acceder a su cuenta y que le permita gestionar sus datos.
- Utiliza un archivo .env para guardar las variables de entorno, 

## Escenario

- El entornmo virtual ya está creado y se ha hecho con uv
- Las librerias Django y django-extension ya estan instaladas