# Enviar vídeo 📹 y audio 🔊 a través de WebRTC

¡Hola developer 👋🏻! En este branch del repo puedes ver cómo enviar vídeo y audio en tiempo real usando WebRTC y forma parte de mi vídeo [Enviar vídeo 📹 y audio 🔊 a través de WebRTC | Cap. 2](https://youtu.be/JPpmUoAlVRI)

[![enviar vídeo y audio a través de webrtc](https://github.com/user-attachments/assets/5330a7aa-82c4-4f88-a837-ab5747c5dbb7)](https://youtu.be/JPpmUoAlVRI)


## ¿Cómo funciona?

1. **Captura de medios**  
   El navegador solicita acceso a la cámara y micrófono del usuario usando la API getUserMedia. Así se obtiene el stream de vídeo y audio local.

2. **Conexión peer-to-peer (P2P)**  
   Se establece una conexión directa entre navegadores usando RTCPeerConnection de WebRTC. Esto permite enviar el vídeo y audio capturados de un usuario a otro sin pasar por un servidor intermedio.

3. **Intercambio de señalización**  
   Para que los dos puntos puedan conectarse, primero intercambian mensajes de señalización (SDP y ICE candidates). En esta demo, el intercambio se realiza a través de un servidor de señalización simple (por ejemplo, usando Python/AIOHTTP y HTTP).

4. **Transmisión en tiempo real**  
   Una vez negociada la conexión, el vídeo y audio fluyen directamente entre los peers. La transmisión es segura y con baja latencia.

5. **Visualización**  
   Los streams de vídeo local y remoto se muestran en la interfaz web usando etiquetas `<video>`, permitiendo la comunicación visual y auditiva en tiempo real.

## Tecnologías utilizadas

- WebRTC (JavaScript) para la comunicación en tiempo real
- Python (AIOHTTP) para la señalización (negociación inicial)
- HTML/CSS para la interfaz

---

¿Te gustaría añadir instrucciones para ejecutar la demo o detalles sobre dependencias? Si necesitas la sección de instalación o uso, dime y te ayudo a escribirla.

## ¿Qué necesitas para empezar? 🛠️

Para ejecutar este proyecto necesitas tener instalado Python 3.9 o superior 🐍.

## Crea un entorno virtual 🛡️

Utiliza un virtual environment para evitar conflictos con otras dependencias de tu sistema.

```bash
python -m venv venv
source venv/bin/activate  # En Linux/Mac
venv\Scripts\activate  # En Windows
``` 

### Instala las dependencias 📦

Instala las dependencias necesarias:

```bash
pip install -r requirements.txt
```

## Crea certificados SSL 🔒

Cuando trabajamos con WebRTC, es necesario utilizar HTTPS y certificados SSL. Puedes generar certificados autofirmados para propósitos de desarrollo.

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

Para ejecutar el proyecto, utiliza el siguiente comando:

```bash
python app.py
```
