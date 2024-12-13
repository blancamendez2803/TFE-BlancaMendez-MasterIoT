# Trabajo Fin de Estudios "Diseño de un sistema IoT para la monitorización y trazabilidad agrícola integrando LoRa e IOTA", por Blanca Méndez López

[id1]: https://github.com/blancamendez2803/TFE-BlancaMendez-MasterIoT.git "GitHub"
[id2]: https://www.arduino.cc/en/software "Arduino IDE"
[id3]: https://wiki.iota.org/iota-sdk/getting-started/python/ "SDK IOTA"


En este repositorio se encuentran:
- Los códigos implementados para realizar las pruebas de validación de la trazabilidad de la información monitorizada por el nodo, así como los programas cargados en el microcontrolador para la realización de las pruebas y para su diseño final. Se pueden descargar desde este repositorio de [GitHub][id1].

A continuación se dedica una sección para indicar cómo descargar los entornos de trabajo que se emplean para ejecutar los códigos, y otra, para explicar brevemente el contenido de los directorios que se encuentran en este repositorio.

# ENTORNOS DE TRABAJO

## Arduino IDE
Para desarrollar e implementar los códigos que se cargan en el microcontrolador, se utiliza el entorno de *Arduino IDE*, que se puede descargar desde el siguiente enlace [Arduino IDE][id2], *versión 2.3.4*.

## SDK de IOTA, Python
Para desarrollar y ejecutar los códigos correspondientes al *middlware* de IOTA, se utiliza su entorno de desarrollo en Python, que se puede instalar siguiendo su propia guía [SDK IOTA][id3], *versión 1.1.4*.


# Directorios
## MCU
Este directorio contiene los códigos que se ejecutan sobre el microcontrolador para realizar diferentes pruebas y simulaciones.

### Config_AHT10_LDR_DS18B20_SEN0308_LORA_SLEEP
Este directorio contiene el código final **Config_AHT10_LDR_DS18B20_SEN0308_LORA_SLEEP.ino** que se carga en el microcontrolador para su instalación en campo. También se ha utilizado para realizar el análisis energético del nodo.

En función de con qué fin se carga en el microcontrolador, se modificará la siguiente línea del código: *const unsigned long SLEEP_TIME = 43200000; // 20 seconds (20000) or 12 hours (43200000) in milliseconds* . Si se pretende cargar el código final completo, se debe utilizar *SLEEP_TIME = 43200000*, ya que configura el tiempo de sueño profundo del nodo en 12 horas, que es el intervalo de tiempo entre ciclos de trabajo. Sin embargo, para realizar el estudio del consumo energético del nodo, el intervalo de tiempo entre ciclos de trabajo era de 20 segundos , por lo que la línea del código sería: *const unsigned long SLEEP_TIME = 20000; // 20 seconds (20000) or 12 hours (43200000) in milliseconds* .

### knownSensors
Este directorio contiene el código **knownSensors.ino** que se carga en el microcontrolador para enviar valores conocidos de sensores simulados a The Things Network (TTN). Se utiliza en las pruebas para validar la trazabilidad de la información desde que se publica en TTN hasta que se confirma en el Tangle de IOTA.

### 8simulatedSensors
Este directorio contiene el código **8sensors.ino** que se carga en el microcontrolador para enviar a TTN valores simulados correspondientes a 8 sensores, utilizado en la *Prueba 3: escalabilidad básica* de la validación de la trazabilidad.

### 10simulatedSensors
Este directorio contiene el código **10simulatedSensors.ino** que se carga en el microcontrolador para enviar a TTN valores simulados correspondientes a 10 sensores, utilizado en la *Prueba 3: escalabilidad básica* de la validación de la trazabilidad.



## middleware
Este directorio contiene los códigos que se ejecutas para realizar las pruebas de validación de la trazabilidad de la información desde que se publican en TTN hasta que se confirman en el Tangle de IOTA.

### Archivo *.env*
Este archivo gestiona las variables de entorno necesarias para configurar las credenciales de TTN y el acceso al nodo de IOTA.

### Prueba 1
Este directorio contiene el código desarrollado para la *Prueba 1: consistencia de datos y tiempo de respuesta* de la trazabilidad de la información y los archivos generados.
- *ttn2iota.py* : es el programa principal desarrollado e implementado para la ejecución de esta prueba.
- *iota_data.csv* : archivo CSV en el que se almacenan los datos de cada transacción.
- *response_times.png* : gráfico con los tiempos de respuesta registrados durante una prueba.

### Prueba 2
Este directorio contiene el código desarrollado para la *Prueba 2: manejo de interrupciones de conexión* de la trazabilidad de la información y los archivos generados.
- *connectionInterrupted.py* : es el programa principal desarrollado e implementado para la ejecución de esta prueba.
- *confirmation_times.csv* : archivo CSV en el que se registran las transacciones confirmadas en el Tangle. 
- *pending_data.csv* : archivo CSV en el que se almacenan los mensajes pendientes de enviar al Tangle por perderse la conexión con la red.

### Prueba 3
Este directorio contiene los códigos desarrollados para la *Prueba 3: escalabilidad básica* de la trazabilidad de la información y los archivos generados.
- *8sensorScalability.py* : es el programa desarrollado e implementado para la ejecución de esta prueba, simulando 8 sensores.
- *iota_data_8sensors.csv* : archivo CSV en el que se almacenan los datos de cada transacción.
- *response_times_8sensors.png* : gráfico con los tiempos de respuesta registrados durante una prueba.
- *10sensorScalability.py* : es el programa desarrollado e implementado para la ejecución de esta prueba, simulando 10 sensores.
- *iota_data_10sensors.csv* : archivo CSV en el que se almacenan los datos de cada transacción.
- *response_times_10sensors.png* : gráfico con los tiempos de respuesta registrados durante una prueba.

### Prueba 4
Este directorio contiene el código desarrollado para la *Prueba 4: uso de credenciales encriptadas* de la trazabilidad de la información y los archivos generados.
- *encryptData.py* : es el programa principal desarrollado e implementado para la ejecución de esta prueba.
- *encryption_metrics.csv* : archivo CSV en el que se registran diferentes métricas sobre la encriptación de la información enviada al Tangle.
- *decryptData.csv* : archivo CSV en el que se registran los datos una vez han sido desencriptados y verificados desde el Tangle.
- *response_times_encryptDecrypt.png* : gráfico con los tiempos de respuesta registrados durante una prueba.

### Prueba 5
Este directorio contiene el código final desarrollado para la *Validación en campo* del nodo y los archivos generados.
- *middlewareFinal.py* : es el programa principal desarrollado e implementado para validar el sistema final de este Trabajo Fin de Estudios.
- *iota_data.csv* : archivo CSV en el que se almacenan los datos correspondientes a cada transacción.
- *encryption_metrics.csv* : archivo CSV en el que se registran diferentes métricas sobre la encriptación de las transacciones enviadas al Tangle.
- *response_times.png* : gráfico con los tiempos de respuesta registrados.
