// Variables globales para almacenar el canal de datos y la conexión peer
var peerConnection = null;
var remoteDataChannel = null;

var connectionId = null;

// Estado del análisis de gestos
var gestureAnalysisActive = false;

// Función para mostrar el badge del estado de conexión
function showConnectionBadge(id) {
    connectionId = id;

    // Remover badge existente si existe
    const existingBadge = document.getElementById("connection-badge");
    if (existingBadge) {
        existingBadge.remove();
    }

    // Crear el badge
    const badge = document.createElement("div");
    badge.id = "connection-badge";
    badge.innerHTML = `🆔 ${id}`;

    // Añadir el badge al body para que sea flotante
    document.body.appendChild(badge);
}

// Función para mostrar el estado de "Conectando..."
function showConnectingBadge() {
    // Remover badge existente si existe
    const existingBadge = document.getElementById("connection-badge");
    if (existingBadge) {
        existingBadge.remove();
    }

    // Crear el badge de conectando
    const badge = document.createElement("div");
    badge.id = "connection-badge";
    badge.innerHTML = `⏳ Conectando...`;
    badge.classList.add("connecting");

    // Añadir el badge al body para que sea flotante
    document.body.appendChild(badge);
}

// Función para actualizar el badge a conectado
function updateBadgeToConnected(id) {
    const existingBadge = document.getElementById("connection-badge");
    if (existingBadge) {
        existingBadge.innerHTML = `🆔 ${id}`;
        existingBadge.classList.remove("connecting");
        existingBadge.classList.add("connected");
    }
}


// Función de log para pintar en consola los mensajes bonitos ✨
function log(message, object) {
    const logElement = document.getElementById("log");
    const timestamp = new Date().toLocaleTimeString();

    let objectHtml = '';
    if (object) {
        if (typeof object === 'string') {
            objectHtml = `<span class="log-string">"${object}"</span>`;
        } else if (typeof object === 'object') {
            objectHtml = `<pre class="log-object">${JSON.stringify(object, null, 2)}</pre>`;
        } else {
            objectHtml = `<span class="log-value">${object}</span>`;
        }
    }

    logElement.innerHTML += `
        <div class="log-entry">
            <span class="log-timestamp">${timestamp}</span>
            <span class="log-message">${message}</span>
            ${objectHtml}
        </div>
    `;

    // Auto-scroll al final
    logElement.scrollTop = logElement.scrollHeight;

    console.log(message, object);
}


// Función para enviar mensajes a través del canal de datos
function sendMessage(message) {
    const channel = dataChannel || remoteDataChannel;
    const sendButton = document.getElementById("send");

    if (channel && channel.readyState === 'open' && !sendButton.disabled) {
        channel.send(message);
        log("📤 Mensaje enviado:", message);
    } else {
        log("⚠️ El canal de datos no está abierto o el botón está deshabilitado");
    }
}

// Mandar el mensaje que se escribe en el input con id "message" cuando se pulsa el botón con id "send"
document.getElementById("send").addEventListener("click", () => {
    const messageInput = document.getElementById("message");
    const message = messageInput.value;
    messageInput.value = ""; // Limpiar el input después de enviar el mensaje
    sendMessage(message);
});

// Mandar el mensaje que se escribe en el input con id "message" cuando se pulsa la tecla Enter
document.getElementById("message").addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        const messageInput = document.getElementById("message");
        const message = messageInput.value;
        sendMessage(message);
        messageInput.value = ""; // Limpiar el input después de enviar el mensaje
    }
});

async function createPeerConnection() {
    //1. Crear la conexión RTCPeerConnection y el canal de datos
    log("🚀 Iniciando conexión WebRTC");

    peerConnection = new RTCPeerConnection({
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" } // Esto nos permite usar un servidor STUN público de Google. 
            // El servidor STUN ayuda a los navegadores a descubrir su dirección IP pública y el puerto que deben usar para comunicarse entre sí.
        ]
    });

    log("🔗 Conexión RTCPeerConnection creada");

    // Solicitar acceso a la cámara y micrófono
    log("🎥 Solicitando acceso a cámara y micrófono...");

    log("📸 Recuperando la cámara seleccionada");
    const cameraSelect = document.getElementById("camera-select");
    if (!cameraSelect.value) {
        log("⚠️ No se ha seleccionado una cámara. Usando la primera cámara disponible.");
        cameraSelect.value = cameraSelect.options[0].value; // Seleccionar la primera cámara si no hay ninguna seleccionada
    }
    log("📸 Cámara seleccionada:", cameraSelect.value);

    const constraints = {
        video: {
            deviceId: cameraSelect.value, // Usar la cámara seleccionada
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 }
        },
        audio: {
            deviceId: "default", // Usar el dispositivo de audio por defecto
            sampleRate: 44100,
            channelCount: 2,
            echoCancellation: true
        }
    };

    const localStream = await navigator.mediaDevices.getUserMedia(constraints);

    // Si tenemos un stream local (video/audio), añadir los tracks
    if (localStream) {
        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });
        log("📹 Tracks de video/audio añadidos a la conexión");
    }


    // Mostrar video local
        const videoElement = document.getElementById('localVideo');
        if (videoElement) {
            videoElement.srcObject = localStream;
            videoElement.style.display = 'block';
        }


    // Configurar el evento para recibir streams remotos
    peerConnection.ontrack = (event) => {
        log("📺 Stream remoto recibido");
        const remoteVideo = document.getElementById("remoteVideo");
        remoteVideo.srcObject = event.streams[0];
    };

    // Crear el canal de datos para enviar mensajes
    log("📡 Creando canal de datos para enviar mensajes");
    dataChannel = peerConnection.createDataChannel("chat");

    // Se configura el evento onopen del canal de datos
    dataChannel.onopen = () => {
        log("🟢 Canal de datos abierto");
        // Habilitar el botón de envío cuando el canal esté abierto
        document.getElementById("send").disabled = false;
    };

    // Se configurar el evento onmessage del canal de datos
    dataChannel.onmessage = (event) => {
        const message = event.data;
        console.log("🔍 DEBUG: Mensaje recibido:", message); // DEBUG LOG

        // Distinguir entre diferentes tipos de mensajes del servidor
        if (message.includes("🤖 Mensaje automático")) {
            log("🕐 Mensaje automático del servidor:", message);
        } else if (message.includes("📢 Echo desde servidor")) {
            log("📢 Echo del servidor:", message);
        } else if (message.includes("🎉")) {
            log("👋 Mensaje de bienvenida:", message);
        } else if (message.startsWith("GESTURE_ANIMATION:")) {
            console.log("🎭 DEBUG: Detectado mensaje de animación:", message); // DEBUG LOG
            // Manejar animación de gesto
            const parts = message.split(":");
            if (parts.length >= 2) {
                const emoji = parts[1];
                const gestureName = parts[2] || "";
                console.log("🎭 DEBUG: Mostrando animación:", emoji, gestureName); // DEBUG LOG
                showGestureAnimation(emoji, gestureName);
            }
        } else if (message.includes("🤏")) {
            log("🤏 Análisis de gestos:", message);
        } else if (message.includes("🆔")) {
            log("🆔 ID de conexión recibido:", message);
            // Si el mensaje contiene un ID de conexión, actualizar el badge a conectado
            const connectionIdReceived = message.split("🆔 ")[1];
            connectionId = connectionIdReceived;
            updateBadgeToConnected(connectionIdReceived);
        } else {
            log("📥 Mensaje recibido:", message);
        }
    };

    // Configurar el evento onclose del canal de datos
    dataChannel.onclose = () => {
        log("🔴 Canal de datos cerrado");
        // Deshabilitar el botón de envío cuando el canal se cierre
        document.getElementById("send").disabled = true;
    };

    // Configurar el evento oniceconnectionstatechange para manejar los cambios en el estado de conexión ICE
    peerConnection.oniceconnectionstatechange = (event) => {
        log("🧊 Estado ICE:", peerConnection.iceConnectionState);

    };

    // Configurar el evento ondatachannel para recibir mensajes del otro extremo
    remoteDataChannel = null;
    peerConnection.ondatachannel = (event) => {

        log("📡 Canal de datos recibido del otro extremo");
        remoteDataChannel = event.channel;

        remoteDataChannel.onmessage = (event) => {
            const message = event.data;
            // Distinguir entre diferentes tipos de mensajes del servidor
            if (message.includes("🤖 Mensaje automático")) {
                log("🕐 Mensaje automático del servidor:", message);
            } else if (message.includes("📢 Echo desde servidor")) {
                log("🔄 Echo del servidor:", message);
            } else if (message.includes("🎉")) {
                log("👋 Mensaje de bienvenida:", message);
            } else if (message.includes("🤏")) {
                log("🤏 Análisis de gestos:", message);
            } else if (message.startsWith("GESTURE_ANIMATION:")) {
                // Manejar animación de gesto
                const parts = message.split(":");
                if (parts.length >= 2) {
                    const emoji = parts[1];
                    const gestureName = parts[2] || "";
                    showGestureAnimation(emoji, gestureName);
                }
            } else if (message.includes("🆔")) {
                log("🆔 ID de conexión recibido:", message);
                // Si el mensaje contiene un ID de conexión, actualizar el badge a conectado
                const connectionIdReceived = message.split("🆔 ")[1];
                connectionId = connectionIdReceived;
                updateBadgeToConnected(connectionIdReceived);
            } else {
                log("💬 Mensaje recibido del servidor:", message);
            }
        };
    };
}

// Función para mostrar animación de gesto sobre el video remoto
function showGestureAnimation(emoji, gestureName = '') {
    // Buscar el contenedor del video remoto
    const remoteVideoWrapper = document.querySelector('#remoteVideo').parentElement;

    if (!remoteVideoWrapper) {
        console.log('⚠️ No se encontró el contenedor del video remoto');
        return;
    }

    // Crear elemento de animación
    const animationElement = document.createElement('div');
    animationElement.className = 'gesture-animation';
    animationElement.textContent = emoji;
    animationElement.title = `Gesto detectado: ${gestureName}`;

    // Posición ligeramente aleatoria para variedad
    const randomX = Math.random() * 40 - 20; // -20px a +20px
    const randomY = Math.random() * 40 - 20; // -20px a +20px
    animationElement.style.top = `calc(50% + ${randomY}px)`;
    animationElement.style.left = `calc(50% + ${randomX}px)`;

    // Agregar al contenedor del video remoto
    remoteVideoWrapper.appendChild(animationElement);

    // Log para debug
    log(`🎭 Mostrando animación: ${emoji} (${gestureName})`);

    // Remover el elemento después de la animación
    setTimeout(() => {
        if (animationElement.parentNode) {
            animationElement.parentNode.removeChild(animationElement);
        }
    }, 4000); // 4 segundos = duración de la animación CSS
}

// Negociar la conexión WebRTC con el servidor
async function negotiate() {


    try {
        log("🤝 Se creará una oferta para iniciar la conexión WebRTC");
        const offer = await peerConnection.createOffer();
        log("📝 Oferta creada:", offer);
        await peerConnection.setLocalDescription(offer);

        // Promesa que espera a que los ICE candidates sean recolectados
        // Esto es importante para asegurarse de que todos los candidatos ICE se hayan recolectado antes de enviar la oferta al servidor.
        // Los ICE candidates son necesarios para establecer la conexión entre los pares.
        // Pueden ser locales o remotos, y se utilizan para encontrar la mejor ruta de comunicación entre los pares.
        // log("⏳ Esperando a que se recolecten todos los ICE candidates...");
        // await new Promise((resolve) => {
        //     peerConnection.onicecandidate = (event) => {
        //         if (event.candidate === null) {
        //             log("✅ Todos los ICE candidates han sido recolectados");
        //             resolve();
        //         } else {
        //             log(`🥇 Nuevo ICE candidate de tipo: ${event.candidate.type}`, event.candidate);
        //         }
        //     };
        // });

        //Enviar la oferta al servidor para hacer la conexión
        const response = await fetch("/offer", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ sdp: peerConnection.localDescription.sdp, type: peerConnection.localDescription.type })
        });

        log("⏳ Oferta enviada al servidor, esperando respuesta...");
        const answer = await response.json();
        log("📬 Respuesta recibida del servidor:", answer);
        log("📜 Configurando la descripción remota con la respuesta del servidor");
        // Esto lo qu hace es configurar la descripción remota de la conexión peer con la respuesta del servidor.
        // El objetivo es establecer la conexión WebRTC entre los pares. Esta indica cómo nos comunicaremos con el otro extremo.
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));

        log("🎉 Conexión WebRTC negociada con éxito");


    } catch (error) {
        log("❌ Error al negociar la conexión WebRTC:", error);
    }
}

// Esta función se ejecuta cuando se hace clic en el botón "Iniciar conexión"
let sessionActive = false;
let localStream = null;

async function start() {
    // Mostrar badge de conectando desde el inicio
    showConnectingBadge();

    // Abrir automáticamente la sección del chat al iniciar conexión
    const chatContent = document.getElementById("chat-content");
    const toggleButton = document.getElementById("toggle-chat");

    if (chatContent.classList.contains("collapsed")) {
        chatContent.classList.remove("collapsed");
        toggleButton.innerHTML = "📝 Ocultar Chat";
        log("💬 Chat abierto al iniciar conexión");
    }

    try {
        // Solicitar acceso a la cámara y micrófono
        log("🎥 Solicitando acceso a cámara y micrófono...");
        const cameraSelect = document.getElementById("camera-select");
        const constraints = {
            video: { deviceId: cameraSelect.value, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } },
            audio: { deviceId: "default", sampleRate: 44100, channelCount: 2, echoCancellation: true }
        };
        localStream = await navigator.mediaDevices.getUserMedia(constraints);
        document.getElementById("localVideo").srcObject = localStream;
        await createPeerConnection(localStream);
        await negotiate();
        sessionActive = true;
        updateStartButton();
    } catch (error) {
        log("❌ Error accediendo a medios:", error.message);
        await createPeerConnection();
        await negotiate();
        sessionActive = true;
        updateStartButton();
    }
}

async function stopSession() {
    log("🛑 Cerrando sesión y grabación...");
    // Avisar al servidor para que detenga la grabación
    try {
        await fetch("/stop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ connectionId })
        });
        log("📡 Aviso de parada enviado al servidor");
    } catch (e) {
        log("⚠️ No se pudo avisar al servidor para detener la grabación", e);
    }
    if (peerConnection) {
        peerConnection.getSenders().forEach(sender => {
            if (sender.track) sender.track.stop();
        });
        peerConnection.close();
        peerConnection = null;
    }
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
    document.getElementById("localVideo").srcObject = null;
    document.getElementById("remoteVideo").srcObject = null;
    sessionActive = false;
    updateStartButton();
    log("✅ Sesión finalizada y recursos liberados.");
}

function updateStartButton() {
    const startButton = document.getElementById("start");
    if (sessionActive) {
        startButton.textContent = "Detener sesión 🛑";
        startButton.onclick = stopSession;
    } else {
        startButton.textContent = "Iniciar conexión 🚀";
        startButton.onclick = start;
    }
}

async function init() {
    // Recuperar todas las cámaras disponibles
    const devices = await navigator.mediaDevices.enumerateDevices();
    log("📸 Dispositivos de medios disponibles:", devices);
    const cameraSelect = document.getElementById("camera-select");
    cameraSelect.innerHTML = '';
    devices.filter(device => device.kind === 'videoinput').forEach(device => {
        const option = document.createElement("option");
        option.value = device.deviceId;
        option.textContent = device.label || `Cámara ${cameraSelect.options.length + 1}`;
        cameraSelect.appendChild(option);
    });
}

window.addEventListener("load", async () => {
    await init();
    updateStartButton();

    // Configurar el botón de colapsar/expandir chat
    const toggleButton = document.getElementById("toggle-chat");
    toggleButton.addEventListener("click", toggleChat);
});