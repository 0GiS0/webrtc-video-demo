import cv2
from aiortc import VideoStreamTrack
import asyncio
import openai
import base64
import time
import json
import re
from rich.console import Console
import os

from dotenv import load_dotenv
from openai import OpenAI


# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Crear cliente de OpenAI
# Asegúrate de tener las variables de entorno ENDPOINT_URL y API_KEY configuradas
client = OpenAI(
    base_url=os.getenv("ENDPOINT_URL"),
    api_key=os.getenv("API_KEY")
)

console = Console()

class GestureAnalysisTrack(VideoStreamTrack):
    """
    Track de video que analiza gestos en tiempo real usando OpenAI Vision API
    """
    
    def __init__(self, track, peer_connection_id, data_channel=None):
        super().__init__()
        self.track = track
        self.peer_connection_id = peer_connection_id
        self.data_channel = data_channel
        self.last_analysis_time = 0
        self.analysis_interval = 5.0  # Analizar cada 5 segundos inicialmente
        self.analysis_enabled = False  # Inicia desactivado
        self.confidence_threshold = 60  # Reducir umbral para detectar más gestos
        
        console.log(f"🤏 GestureAnalysisTrack creado para {peer_connection_id} - Canal: {'✅' if data_channel else '❌'}")
        console.log(f"🤏 Configuración inicial: intervalo={self.analysis_interval}s, umbral={self.confidence_threshold}%")
        
    async def recv(self):
        """Recibe frame y opcionalmente lo analiza"""
        frame = await self.track.recv()
        
        # Solo analizar si está habilitado
        if self.analysis_enabled:
            current_time = time.time()
            if current_time - self.last_analysis_time >= self.analysis_interval:
                self.last_analysis_time = current_time
                console.log(f"🔍 Frame disponible para análisis - {self.peer_connection_id} (habilitado: {self.analysis_enabled})")
                # Analizar de forma asíncrona para no bloquear el video
                asyncio.create_task(self.analyze_frame(frame))
        
        return frame
    
    async def analyze_frame(self, frame):
        """Analiza un frame para detectar gestos"""
        try:
            console.log(f"🔍 Iniciando análisis de frame para {self.peer_connection_id}")
            
            # Convertir frame a imagen BGR
            img = frame.to_ndarray(format="bgr24")
            console.log(f"📏 Dimensiones del frame: {img.shape}")
            
            # Redimensionar para optimizar (opcional)
            height, width = img.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height))
                console.log(f"📏 Frame redimensionado a: {new_width}x{new_height}")
            
            # Convertir a JPEG y base64
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            console.log(f"📸 Frame convertido a base64 ({len(img_base64)} caracteres)")
            
            # Analizar con OpenAI
            console.log(f"🤖 Enviando a OpenAI para análisis...")
            result = await self.analyze_with_openai(img_base64)
            
            # Solo reportar si supera el umbral de confianza
            if result.get('gesture') and result.get('confidence', 0) >= self.confidence_threshold:
                console.log(f"✅ Gesto detectado: {result}")
                await self.send_gesture_result(result)
            else:
                console.log(f"⚪ No se detectó gesto válido o baja confianza: {result}")
                
        except Exception as e:
            console.log(f"❌ Error analizando frame para {self.peer_connection_id}: {e}")
            import traceback
            console.log(f"📍 Traceback: {traceback.format_exc()}")
    
    async def analyze_with_openai(self, image_base64):
        """Envía imagen a OpenAI Vision API para análisis de gestos"""
        try:
            console.log(f"🧠 Modelo para analizar {os.getenv('MODEL')}")
            console.log(f"🧠 Endpoint para analizar {os.getenv('ENDPOINT_URL')}")
            
            
            # Medir tiempo de respuesta
            start_time = time.time()
            console.log(f"🕒 Enviando imagen a OpenAI para análisis...")
            
            response = client.chat.completions.create(
                model=os.getenv("MODEL"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """🤏 Analiza esta imagen y detecta gestos de manos.
                                
                                Responde ÚNICAMENTE con un JSON válido en este formato:
                                {
                                    "gesture": "nombre_del_gesto",
                                    "confidence": 85,
                                    "description": "breve descripción",
                                    "emoji": "👍"
                                }
                                
                                Gestos a detectar:
                                - 👍 pulgar_arriba
                                - 👎 pulgar_abajo  
                                - 👌 ok
                                - ✌️ paz
                                - ✊ puño
                                - ✋ stop
                                - 👋 saludo
                                - 🤟 rock
                                - 🤏 pellizco
                                - 👏 aplauso
                                
                                Si no hay gestos claros, usa "gesture": null"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=200,
                temperature=0.1
            )
            console.log(f"🕒 Tiempo de respuesta: {time.time() - start_time:.2f} segundos")
            result_text = response.choices[0].message.content.strip()
            
            # Extraer JSON de la respuesta
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                console.log(f"🤏 Análisis completado: {result.get('gesture', 'none')} ({result.get('confidence', 0)}%)")
                return result
            else:
                console.log(f"⚠️ No se pudo parsear respuesta de OpenAI: {result_text}")
                return {"gesture": None, "confidence": 0}
                
        except json.JSONDecodeError as e:
            console.log(f"❌ Error parseando JSON de OpenAI: {e}")
            return {"gesture": None, "confidence": 0}
        except Exception as e:
            console.log(f"❌ Error con OpenAI Vision API: {e}")
            return {"gesture": None, "confidence": 0}
    
    async def send_gesture_result(self, result):
        """Envía el resultado del análisis por el canal de datos"""
        if not self.data_channel:
            console.log(f"⚠️ No hay canal de datos para enviar gesto a {self.peer_connection_id}")
            return
            
        try:
            gesture_msg = (
                f"🤏 IA detectó: {result.get('emoji', '🤏')} {result['gesture']} "
                f"({result['confidence']}% confianza) - {result.get('description', '')}"
            )
            
            self.data_channel.send(gesture_msg)
            console.log(f"🤏 Gesto enviado a {self.peer_connection_id}: {result['gesture']}")
            
        except Exception as e:
            console.log(f"❌ Error enviando gesto a {self.peer_connection_id}: {e}")
    
    def set_data_channel(self, channel):
        """Establece el canal de datos para enviar resultados"""
        self.data_channel = channel
        console.log(f"📡 Canal de datos configurado para análisis de gestos de {self.peer_connection_id}")
    
    def enable_analysis(self):
        """Activa el análisis de gestos"""
        self.analysis_enabled = True
        console.log(f"🟢 Análisis de gestos activado para {self.peer_connection_id}")
        # Enviar mensaje de prueba inmediatamente
        if self.data_channel:
            test_msg = f"🤏 ¡Análisis de gestos iniciado! Canal OK para {self.peer_connection_id}"
            self.data_channel.send(test_msg)
            console.log(f"✅ Mensaje de prueba enviado: {test_msg}")
    
    def disable_analysis(self):
        """Desactiva el análisis de gestos"""
        self.analysis_enabled = False
        console.log(f"🔴 Análisis de gestos desactivado para {self.peer_connection_id}")
    
    def set_analysis_interval(self, interval):
        """Cambia el intervalo de análisis"""
        self.analysis_interval = max(1.0, interval)  # Mínimo 1 segundo
        console.log(f"⏱️ Intervalo de análisis cambiado a {self.analysis_interval}s para {self.peer_connection_id}")
    
    def set_confidence_threshold(self, threshold):
        """Cambia el umbral de confianza"""
        self.confidence_threshold = max(0, min(100, threshold))  # Entre 0 y 100
        console.log(f"🎯 Umbral de confianza cambiado a {self.confidence_threshold}% para {self.peer_connection_id}")


class GestureAnalyzer:
    """
    Clase utilitaria para configurar y gestionar el análisis de gestos
    """
    
    @staticmethod
    def create_track(original_track, peer_connection_id, data_channel=None):
        """Crea un track de análisis de gestos"""
        return GestureAnalysisTrack(original_track, peer_connection_id, data_channel)
    
    @staticmethod
    def configure_openai(api_key):
        """Configura la API key de OpenAI"""
        client.api_key = api_key
        console.log("🔑 OpenAI API configurada para análisis de gestos")