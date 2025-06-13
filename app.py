import ssl
import asyncio
import datetime
import socket
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from rich.console import Console
from aiohttp import web
import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from gesture_analyzer import GestureAnalysisTrack


# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Crear cliente de OpenAI
# Asegúrate de tener las variables de entorno ENDPOINT_URL y API_KEY configuradas
client = OpenAI(
    base_url=os.getenv("ENDPOINT_URL"),
    api_key=os.getenv("API_KEY")
)


# Crea la aplicación web con aiohttp
app = web.Application()
# Configura la consola para imprimir mensajes
console = Console()

ROOT = os.path.dirname(os.path.abspath(__file__))

# Diccionario para almacenar conexiones activas
active_connections = set()

# Media relay para manejar múltiples flujos de medios
media_relay = MediaRelay()

# Función para enviar mensajes periódicos
async def send_periodic_messages(channel, peer_connection_id):
    """Envía mensajes automáticos cada 30 segundos para demostrar comunicación bidireccional"""
    count = 1
    try:
        while True:
            await asyncio.sleep(30)  # Esperar 30 segundos
            
            if channel.readyState == 'open':
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                message = f"🤖 Mensaje automático #{count} desde el servidor - {timestamp}"
                channel.send(message)
                console.log(f"🕐 Mensaje automático enviado a {peer_connection_id}: {message}")
                count += 1
            else:
                console.log(f"🔴 Canal cerrado para {peer_connection_id}, deteniendo mensajes automáticos")
                # Si el canal está cerrado, se elimina al peer de la lista de conexiones activas
                console.log(f"🗑️ Eliminando {peer_connection_id} de conexiones activas")
                active_connections.discard(peer_connection_id)
                console.log(f"📊 Conexiones activas: {len(active_connections)}")
                break
                
    except Exception as e:
        console.log(f"❌ Error enviando mensajes automáticos para {peer_connection_id}: {e}")


async def home(request):
    """Para servir la página HTML principal"""
    return web.FileResponse('static/index.html')


async def offer(request):
    """
    Maneja la señalización WebRTC para establecer una conexión con un cliente.
    Recibe una oferta SDP del cliente, crea un RTCPeerConnection, y devuelve una respuesta SDP.
    """
    
    # Recupera los parametros de la solicitud
    params = await request.json()

    offer_sdp = RTCSessionDescription(
        sdp=params['sdp'],
        type=params['type']
    )

    peer_connection = RTCPeerConnection()

    peer_connection_id = f"peer_connection_{id(peer_connection)}"

    active_connections.add(peer_connection_id)

    console.log(f"📊 Conexiones activas: {len(active_connections)}")
    console.log(f"🆔 ID de conexión peer: {peer_connection_id}")

    console.log(f"🔗 Nueva conexión establecida: {peer_connection_id}")
    console.log(f"📄 Oferta SDP:\n{offer_sdp.sdp}")
    
    # Log la oferta SDP para revisar candidatos ICE
    if 'a=candidate' in offer_sdp.sdp:
        console.log("✅ La oferta SDP contiene candidatos ICE.")
    else:
        console.log("❌ La oferta SDP NO contiene candidatos ICE.")

    # Canal para la comunicación bidireccional de datos
    data_channel = peer_connection.createDataChannel("chat")
    
    # Almacenar el canal de datos en el peer_connection para acceso global
    peer_connection.data_channel = data_channel

    # Este evento se dispara cuando se crea un canal de datos
    @peer_connection.on('datachannel')
    def on_data_channel(channel):
        console.log(f"📡 Canal de datos creado: {channel.label}")
        # Se manda el primer mensaje al canal de datos
        channel.send("🎉 ¡Hola desde el servidor! La conexión bidireccional está establecida.")
        channel.send(f"🆔 ID de conexión: {peer_connection_id}")
        
        # Iniciar mensajes automáticos cada 30 segundos
        asyncio.create_task(send_periodic_messages(channel, peer_connection_id))
        console.log(f"⏰ Mensajes automáticos iniciados para {peer_connection_id}")

        # Este evento se dispara cuando se recibe un mensaje en el canal de datos
        @channel.on('message')
        def on_message(message):
            console.log(f"📩 Mensaje recibido: {message}")
            
            # Manejar comandos de análisis de gestos
            if message.startswith("🤏 start_gesture_analysis"):
                console.log("🟢 Comando: activar análisis de gestos")
                if hasattr(peer_connection, 'gesture_analyzer'):
                    peer_connection.gesture_analyzer.enable_analysis()
                    # Asegurar que el canal esté configurado
                    if not peer_connection.gesture_analyzer.data_channel:
                        peer_connection.gesture_analyzer.set_data_channel(channel)
                    channel.send("🤏 ✅ Análisis de gestos activado en el servidor")
                    console.log(f"🤏 Análisis de gestos activado para {peer_connection_id}")
                else:
                    channel.send("🤏 ❌ No hay analizador de gestos disponible")
                    console.log(f"❌ No se encontró analizador de gestos para {peer_connection_id}")
                return
                
            elif message.startswith("🤏 stop_gesture_analysis"):
                console.log("� Comando: desactivar análisis de gestos")
                if hasattr(peer_connection, 'gesture_analyzer'):
                    peer_connection.gesture_analyzer.disable_analysis()
                    channel.send("🤏 ⏸️ Análisis de gestos desactivado en el servidor")
                    console.log(f"🤏 Análisis de gestos desactivado para {peer_connection_id}")
                else:
                    channel.send("🤏 ❌ No hay analizador de gestos disponible")
                    console.log(f"❌ No se encontró analizador de gestos para {peer_connection_id}")
                return
            
            # Si no es un comando de gestos, procesar como mensaje normal con IA
            try:
                response = client.chat.completions.create(
                    model=os.getenv("MODEL_FOR_CHAT"),
                    messages=[
                        {"role": "system", "content": "Eres un asistente útil."},
                        {"role": "user", "content": message}
                    ]
                )
                response_message = response.choices[0].message.content
                console.log(f"🤖 Respuesta del modelo: {response_message}")
                channel.send(f"🤖 Respuesta del modelo: {response_message}")
            except Exception as e:
                console.log(f"❌ Error con IA: {e}")
                channel.send(f"📢 Echo desde servidor: {message}")

        # Este evento se dispara cuando el canal de datos se cierra
        @data_channel.on('close')
        def on_data_channel_close():
            console.log("🔴 Canal de datos cerrado")
            # Se elimina al peer de la lista de conexiones activas
            console.log(f"🗑️ Eliminando {peer_connection_id} de conexiones activas")
            active_connections.discard(peer_connection_id)
            console.log(f"📊 Conexiones activas: {len(active_connections)}")

    # Eventos para manejar el estado de la conexión
    @peer_connection.on('connectionstatechange')
    def on_connection_state_change():
        console.log(f"🔄 Estado de la conexión cambiado: {peer_connection.connectionState}")

    # Este evento se dispara cuando se recibe una pista de medios. Puede ser audio, video, etc.
    @peer_connection.on('track')
    def on_track(track):
        console.log(f"🎵 Pista recibida: {track.kind}")
        
        # Analizar video en busca de gestos o acciones
        if track.kind == 'video':
            console.log("📹 Procesando video para detección de gestos...")

            # Se crea una instancia de GestureAnalysisTrack para analizar la pista de video
            # Pasamos el canal de datos si está disponible
            data_channel = getattr(peer_connection, 'data_channel', None)
            gesture_analyzer = GestureAnalysisTrack(track, peer_connection_id, data_channel)
            
            # Almacenar la referencia en el peer_connection para accederla desde los mensajes
            peer_connection.gesture_analyzer = gesture_analyzer
            
            console.log(f"🤏 Analizador de gestos creado para {peer_connection_id} con canal: {data_channel is not None}")
        
            # Enviar de vuelta la pista de video al cliente usando el analizador
            peer_connection.addTrack(gesture_analyzer)
            console.log("🔄 Pista de video reenviada al cliente con análisis de gestos")
            

            @track.on('ended')
            def on_track_ended():
                console.log("🔴 Pista de video finalizada")
                # Se elimina al peer de la lista de conexiones activas
                console.log(f"🗑️ Eliminando {peer_connection_id} de conexiones activas")
                active_connections.discard(peer_connection_id)
                console.log(f"📊 Conexiones activas: {len(active_connections)}")

        

    # Se establece la descripción remota. Es decir, la oferta SDP que se recibe del cliente.
    await peer_connection.setRemoteDescription(offer_sdp)
    # Se crea una respuesta SDP (SDP Answer) para enviar de vuelta al cliente.
    answer = await peer_connection.createAnswer()
    # Y se establece la descripción local con la respuesta SDP.
    await peer_connection.setLocalDescription(answer)

    console.log(f"📝 Respuesta SDP: {peer_connection.localDescription.sdp}")
    
    # La respuesta se envía al cliente con la SDP generada
    return web.Response(
            content_type="application/json",
            text=json.dumps({"sdp": peer_connection.localDescription.sdp, "type": peer_connection.localDescription.type}),
        )

# Función para obtener la IP de la red privada
def get_private_ip():
    """Obtiene la IP de la red privada para conexiones desde otros equipos"""
    try:
        # Crear un socket temporal para obtener la IP local
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Conectar a una dirección remota (no necesita estar accesible)
            s.connect(("8.8.8.8", 80))
            private_ip = s.getsockname()[0]
            return private_ip
    except Exception as e:
        console.log(f"❌ Error obteniendo IP privada: {e}")
        return "No disponible"

ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

app.router.add_static('/static/', os.path.join(ROOT, 'static'), show_index=True)  # Archivos estáticos
app.router.add_get('/', home)
app.router.add_post('/offer', offer)


if __name__ == '__main__':
    # Obtener la IP de la red privada
    private_ip = get_private_ip()
    port = 8000
    
    console.log("🚀 Iniciando servidor WebRTC...")
    console.log("=" * 60)
    console.log("📡 URLs de acceso:")
    console.log(f"🏠 Local:        https://localhost:{port}")
    console.log(f"🌐 Red privada:  https://{private_ip}:{port}")
    console.log("=" * 60)
    console.log("📝 Nota: Para conectar desde otro equipo, usa la URL de red privada")
    console.log("🔒 Asegúrate de que el certificado SSL sea aceptado en el navegador")
    console.log("🔥 Si tienes problemas de acceso, verifica:")
    console.log("   • Firewall del sistema (puerto 8000 abierto)")
    console.log("   • Ambos dispositivos en la misma red WiFi")
    console.log("   • Acepta el certificado SSL 'inseguro' en el navegador")
    console.log("=" * 60)
    
    web.run_app(app, host='0.0.0.0', port=port, ssl_context=ssl_context)
