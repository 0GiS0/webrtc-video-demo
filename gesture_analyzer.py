import cv2
from aiortc import VideoStreamTrack
import asyncio
import base64
import time
import json
import re
from rich.console import Console
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from openai import OpenAI


# Cargar variables de entorno desde el archivo .env
load_dotenv(override=True)

# Crear cliente de OpenAI
# Asegúrate de tener las variables de entorno ENDPOINT_URL y API_KEY configuradas
client = OpenAI(
    base_url=os.getenv("ENDPOINT_URL"),
    api_key=os.getenv("API_KEY")    
)

console = Console()

class GestureAnalysisTrack(VideoStreamTrack):
    """
    Track de video que analiza gestos en tiempo real usando modelos de inteligencia artificial generativa
    """
    
    def __init__(self, track, peer_connection_id, data_channel=None):
        super().__init__()
        self.track = track
        self.peer_connection_id = peer_connection_id
        self.data_channel = data_channel
        self.last_analysis_time = 0
        self.analysis_interval = 2.0  # Analizar cada 8 segundos para reducir lag
        self.analysis_enabled = False  # Inicia desactivado
        self.confidence_threshold = 60  # Reducir umbral para detectar más gestos
        self.analyzing = False  # Flag para evitar análisis simultáneos
        self.frame_skip_count = 0  # Contador para saltar frames
        self.executor = ThreadPoolExecutor(max_workers=1)  # Un solo hilo para análisis
        
        console.log(f"🤏 GestureAnalysisTrack creado para {peer_connection_id} - Canal: {'✅' if data_channel else '❌'}")
        console.log(f"🤏 Configuración inicial: intervalo={self.analysis_interval}s, umbral={self.confidence_threshold}%")
        
    async def recv(self):
        """Recibe un frame y, si corresponde, inicia análisis de gestos en background sin bloquear"""
        frame = await self.track.recv()
        
        # Solo analizar si está habilitado y no hay análisis en curso
        if self.analysis_enabled and not self.analyzing:
            current_time = time.time()
            
            # Saltar frames ocasionalmente para mantener fluidez
            self.frame_skip_count += 1
            if (current_time - self.last_analysis_time >= self.analysis_interval and 
                self.frame_skip_count % 10 == 0):  # Solo cada 10 frames
                
                self.last_analysis_time = current_time
                self.analyzing = True
                
                # Procesar en background sin bloquear
                asyncio.create_task(self._analyze_frame_background(frame))
        
        # Siempre devolver el frame inmediatamente
        return frame
    
    async def analyze_frame(self, frame):
        """Analiza un frame para detectar gestos"""
        try:
            console.log(f"🔍 Iniciando análisis de frame para {self.peer_connection_id}")
            
            # Convertir frame a imagen BGR
            img = frame.to_ndarray(format="bgr24")
            console.log(f"📏 Dimensiones del frame: {img.shape}")
            
            # Redimensionar para optimizar
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

            # Analizar con IA
            console.log(f"🤖 Enviando a IA para análisis...")
            result = await self.analyze_with_ai(img_base64)

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
    
    async def analyze_with_ai(self, image_base64):
        """Envía imagen a un modelo de IA para análisis de gestos"""
        try:
            console.log(f"🧠 Modelo para analizar {os.getenv('MODEL')}")
            console.log(f"🧠 Endpoint para analizar {os.getenv('ENDPOINT_URL')}")
            
            # Medir tiempo de respuesta
            start_time = time.time()
            console.log(f"🕒 Enviando imagen ({len(image_base64)} chars) a IA para análisis...")

            # response = client.chat.completions.create(
            #     model="openai/gpt-4.1-mini",
            #     messages=[
            #         {
            #             "role": "user",
            #             "content": [
            #                 {
            #                     "type": "text",
            #                     "text": """🤏 Analiza esta imagen y detecta gestos de manos claramente visibles.
                                
            #                     Responde ÚNICAMENTE con un JSON válido en este formato:
            #                     {
            #                         "gesture": "nombre_del_gesto",
            #                         "confidence": 85,
            #                         "description": "breve descripción",
            #                         "emoji": "👍"
            #                     }
                                
            #                     Gestos a detectar (solo si son muy claros y evidentes):
            #                     - 👍 pulgar_arriba (pulgar hacia arriba, otros dedos cerrados)
            #                     - 👎 pulgar_abajo (pulgar hacia abajo, otros dedos cerrados)
            #                     - 👌 ok (círculo con pulgar e índice, otros dedos extendidos)
            #                     - ✌️ victoria (índice y medio extendidos en V, otros cerrados)
            #                     - ✊ puño (todos los dedos cerrados en puño)
            #                     - ✋ stop (palma abierta hacia la cámara, dedos extendidos)
            #                     - 👋 saludo (mano abierta moviéndose o en posición de saludo)
            #                     - 🤟 rock (meñique, índice y pulgar extendidos)
            #                     - 🤏 pellizco (pulgar e índice casi tocándose)
            #                     - 👏 aplauso (dos manos aplaudiendo o palmas juntas)
            #                     - 🤝 apretón (dos manos juntas en saludo)
            #                     - 🙏 gracias (palmas juntas en posición de oración)
            #                     - 🤘 rock_on (índice y meñique extendidos)
            #                     - 🫶 corazón (manos formando un corazón)
            #                     - 👊 puño_cerrado (puño hacia adelante)
                                
            #                     IMPORTANTE: Solo detecta gestos si la confianza es mayor al 70%. Si no hay gestos claros o la imagen es borrosa, usa "gesture": null"""
            #                 },
            #                 {
            #                     "type": "image_url",
            #                     "image_url": {
            #                         "url": f"data:image/jpeg;base64,{image_base64}"
            #                     }
            #                 }
            #             ]
            #         }
            #     ],
            #     max_tokens=200,
            #     temperature=0.1
            # )
            
            
            response = client.responses.create(
                model=os.getenv("MODEL"),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": """🤏 Analiza esta imagen y detecta gestos de manos claramente visibles.
                                
                                Responde ÚNICAMENTE con un JSON válido en este formato:
                                {
                                    "gesture": "nombre_del_gesto",
                                    "confidence": 85,
                                    "description": "breve descripción",
                                    "emoji": "👍"
                                }
                                
                                Gestos a detectar (solo si son muy claros y evidentes):
                                - 👍 pulgar_arriba (pulgar hacia arriba, otros dedos cerrados)
                                - 👎 pulgar_abajo (pulgar hacia abajo, otros dedos cerrados)
                                - 👌 ok (círculo con pulgar e índice, otros dedos extendidos)
                                - ✌️ victoria (índice y medio extendidos en V, otros cerrados)
                                - ✊ puño (todos los dedos cerrados en puño)
                                - ✋ stop (palma abierta hacia la cámara, dedos extendidos)
                                - 👋 saludo (mano abierta moviéndose o en posición de saludo)
                                - 🤟 rock (meñique, índice y pulgar extendidos)
                                - 🤏 pellizco (pulgar e índice casi tocándose)
                                - 👏 aplauso (dos manos aplaudiendo o palmas juntas)
                                - 🤝 apretón (dos manos juntas en saludo)
                                - 🙏 gracias (palmas juntas en posición de oración)
                                - 🤘 rock_on (índice y meñique extendidos)
                                - 🫶 corazón (manos formando un corazón)
                                - 👊 puño_cerrado (puño hacia adelante)
                                
                                IMPORTANTE: Solo detecta gestos si la confianza es mayor al 70%. Si no hay gestos claros o la imagen es borrosa, usa "gesture": null"""
                            },
                            {
                                "type": "input_image",
                                "image_url":  f"data:image/jpeg;base64,{image_base64}"                                
                            }
                        ]
                    }
                ]
            )
            
            console.log(f"🕒 Tiempo de respuesta: {time.time() - start_time:.2f} segundos")
            # result_text = response.choices[0].message.content.strip()
            result_text = response.output_text
            
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
            console.log(f"❌ Error parseando JSON de IA: {e}")
            return {"gesture": None, "confidence": 0}
        except Exception as e:
            console.log(f"❌ Error con IA: {e}")
            return {"gesture": None, "confidence": 0}
    
    async def send_gesture_result(self, result):
        """Envía el resultado del análisis por el canal de datos"""
        if not self.data_channel:
            console.log(f"⚠️ No hay canal de datos para enviar gesto a {self.peer_connection_id}")
            return
            
        try:
            # Mensaje para el chat normal
            gesture_msg = (
                f"🤏 IA detectó: {result.get('emoji', '🤏')} {result['gesture']} "
                f"({result['confidence']}% confianza) - {result.get('description', '')}"
            )
            
            # Mensaje especial para activar animación
            animation_msg = f"GESTURE_ANIMATION:{result.get('emoji', '🤏')}:{result['gesture']}"
            
            console.log(f"📤 Enviando mensaje de gesto: {gesture_msg}")
            console.log(f"📤 Enviando mensaje de animación: {animation_msg}")
            console.log(f"📡 Estado del canal: readyState={getattr(self.data_channel, 'readyState', 'unknown')}")
            
            self.data_channel.send(gesture_msg)
            self.data_channel.send(animation_msg)
            console.log(f"✅ Mensajes enviados exitosamente a {self.peer_connection_id}")
            
        except Exception as e:
            console.log(f"❌ Error enviando gesto a {self.peer_connection_id}: {e}")
            import traceback
            console.log(f"📍 Traceback completo: {traceback.format_exc()}")
    
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
            
            # Enviar también una animación de prueba
            test_animation = "GESTURE_ANIMATION:🎯:test_activation"
            self.data_channel.send(test_animation)
            console.log(f"🎯 Animación de prueba enviada: {test_animation}")
        else:
            console.log(f"❌ No hay canal de datos disponible para enviar mensaje de prueba")
    
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
    
    async def _analyze_frame_background(self, frame):
        """Analiza un frame en background usando ThreadPoolExecutor"""
        try:
            console.log(f"🔍 Iniciando análisis en background para {self.peer_connection_id}")
            
            # Ejecutar el procesamiento pesado en un hilo separado
            loop = asyncio.get_event_loop()
            frame_data = await loop.run_in_executor(
                self.executor, 
                self._process_frame_sync, 
                frame
            )
            
            if frame_data and frame_data.get('image_base64'):
                # Analizar con OpenAI de forma asíncrona
                result = await self.analyze_with_ai(frame_data['image_base64'])
                
                # Solo reportar si supera el umbral de confianza
                if result and result.get('gesture') and result.get('confidence', 0) >= self.confidence_threshold:
                    console.log(f"✅ Gesto detectado en background: {result}")
                    await self.send_gesture_result(result)
                else:
                    console.log(f"⚪ Análisis completado sin gestos detectados")
            
        except Exception as e:
            console.log(f"❌ Error en análisis background para {self.peer_connection_id}: {e}")
        finally:
            self.analyzing = False  # Liberar el flag
    
    def _process_frame_sync(self, frame):
        """Procesa el frame de forma síncrona en un hilo separado"""
        try:
            # Convertir frame a imagen BGR con resolución reducida
            img = frame.to_ndarray(format="bgr24")
            
            # Reducir significativamente la resolución para análisis más rápido
            height, width = img.shape[:2]
            target_width = 320  # Resolución muy reducida
            if width > target_width:
                scale = target_width / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height))
            
            # Convertir a JPEG con calidad reducida para análisis más rápido
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            console.log(f"📸 Frame procesado: {new_width}x{new_height}, {len(img_base64)} chars")
            
            return {'image_base64': img_base64}
            
        except Exception as e:
            console.log(f"❌ Error procesando frame: {e}")
            return None

    def cleanup(self):
        """Limpia recursos del analizador"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
            console.log(f"🧹 Recursos limpiados para {self.peer_connection_id}")

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