# Especificaciones del proyecto

## Objetivo

El objetivo es crear una aplicacion para la gestión de la salud, necesito un dashboard como página principal que refleje los ultimos de todas las mediciones, graficas de seguimiento y deduzca patrones de comportamiento en función de los datos registrados

Las medidas que va a tener en cuenta son el peso y la tensión arterial

Para control de la tensión arterial, se realizaran tres medidas consecutivas y la media, será la medida real

- El control de la tensión se divide en dos escenarios, el primero es una medición intensa en la que e realizan dos medidas de tensión durante el dia, una por la mañana y otra por la noche.
- El otro escenario, es el de medidas de control, que se realizaran de vez en cuando (mañana o tarde), el sistema de medición es el mismo, 3 medidas y calculo de la media.
- La pantalla de seguimientoo historial de todas las medidas de tensión, reflejará las tres medidas, la media y se realizará el cálculo del error relativo y error absoluto de cada medida con respecto de la media que será considerada como valor real

Para el control del peso, se realizaran medidas esporádicas y se controlara la diferencia en el peso de cada medida con la anterior, asi como la total acumulada con la medida inicial

Habra otra aplicación dentro del proyecto que tendrá que ver con los alimentos y sus características nutricionales, en el modelo de datos, cada aliemnto tendrá los mismos campos, estos se utilizaran para llevar un control de las calorias consumidas en cada ingesta de comida

Tendremos otra tabla con los mismos datos para la composición nutricional, a modo de valores referencia, pero con los valores recomendados para hombres y mujeres, que se utilizarán para los cálculos del control de calorias y las necesidades personales

Se tendrá en cuenta las siguientes entradas de datos:

- Las medidas de tensioón arterial
- La medida de peso
- Las tomas de suplementos alimenticiones
- La ingesta de alimentos, para está medida, se tendrá en cuenta lo consumido para su cálculo nutricional y calórico, con el objetivo de la obtención de patrones en función de los resultados

Habrá otra aplicación que será de recetas de comida, en la que se tendrán en cuenta, los ingredientes y la receta de la preparación. Se calculará la composición nutricional de los ingredientes así como su equivalente calórico


Ambos escenarios tendrá páginas de seguimiento separadas, una para la medición intensa y otra para la medición de control.

## Procedimiento

Cada medición consta de 3 pruebas que se realizarán consecutivas y el valor a tener en cuenta para mostrar en una gráfica de velas sera la media de las tres medidas, los valores tomados, sera la presión sistólica, la presión diastólica y las pulsaciones. Y se tendrá en cuenta

- Si la medida es por la mañana o por la noche
- Si la medida es de control o de medición intensa
- Estado de ánimo
- Se deberá tener un valor booleano que indique cuando se ha comido fuera de casa

Para la aplicación de Alimentos y sus caracteristicas nutricionales, el modelo de datos deberá contener los siguientes campos:

- Categoria del alimento, por ejemplo, verduras, lacteos, pescados, carnes, etc. que será seleccionable por el usuario
- Alimento
- Descripción
- Estacionalidad
- Porción comestible
- Valoración nutricional
- Composición nutricional por 100 gr o por ración 250gr, que pueden tener un valor o no, por lo que ese campo puede tener un valor en blanco

    - Energia en Kilocalorias
    - Proteinas en gramos
    - Lipidos totales en gramos
    - Colesterol en miligramos por 1000 kilocalorias
    - Hidratos de carbono en gramos
    - Fibra en gramos
    - Agua en gramos
    - Calcio en miligramos
    - Hierro en miligramos
    - Yodo en microgramos
    - Magnesio en miligramos
    - Zinc en miligramos
    - Sodio en miligramos
    - Potasio en miligramos
    - Fósforo en miligramos
    - Selenio en microgramos
    - Tiamina en miligramos
    - Riboflavina en miligramos
    - Vitamina B6 en miligramos
    - Folatos en microgramos
    - Vitamina B12 en microgramos
    - Vitamina C en miligramos
    - Vitamina A en microgramos
    - Vitamina D en microgramos
    - Vitamina E en miligramos

- Toma de suplementos y complejos vitaminicos, estos, tendrán un modelo de datos a parte y serán añadidos por cada usuario de la aplicación, se tendrá en cuenta cual se toma y cuando, de forma que se pueda estudiar para obtener el patrón de los resultados de las medidas 

- Tipo de actividad física, que será configurable y seleccionable por el usuario, podran ser diferentes actividades como  andar, gimnasio, karate, tenis, etc... y también será utilizable para el estudio de patrones de salud
- Observaciones

Con todos estos datos se puede estudiar un patron de variabilidad de la tensión y del peso en función de esos datos. 

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