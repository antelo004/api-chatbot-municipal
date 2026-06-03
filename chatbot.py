"""
chatbot.py — Servidor Flask para el Chatbot del Municipio de Riberalta
=====================================================================
Requisitos en tu entorno aislado (.venv):
    pip install flask flask-cors flask-limiter openai python-dotenv

Arrancar:
    python chatbot.py

El servidor escucha en http://127.0.0.1:5000
Endpoint: POST /chat   →  { "mensaje": "..." }  →  { "respuesta": "..." }
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from openai import OpenAI
import os
from datetime import datetime

# 1. Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

# CORS restringido: solo tu sitio de Netlify y localhost para desarrollo
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
CORS(app, origins=allowed_origins)

# Rate limiting: máximo 30 peticiones por minuto por IP
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# 2. Inicializar el cliente oficial conectado a la nube gratuita de Groq
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

# 3. FILTRO HÍBRIDO: Respuestas locales inmediatas (Costo $0 y velocidad instantánea)
RESPUESTAS_LOCALES = {
    ("hola", "buenas", "buen día", "saludos"): (
        "¡Hola pariente! 👋 Soy Libélulin, tu asistente virtual del Gobierno Autónomo Municipal de Riberalta. "
        "¿En qué te puedo colaborar el día de hoy?"
    ),
    ("horario", "atienden", "hora", "horarios", "abren", "cierran"): (
        "🕐 ¡Claro que sí! El Gobierno Autónomo Municipal de Riberalta te atiende de lunes a viernes "
        "de 08:00 a 12:00 por la mañanita, y de 14:00 a 18:00 por la tarde."
    ),
    ("dirección", "dónde", "ubicación", "queda", "plaza", "alcaldia"): (
        "📍 La alcaldía central se encuentra ubicada frente a la Plaza Principal de Riberalta, "
        "en pleno centro de nuestra hermosa región amazónica."
    ),
    ("teléfono", "número", "llamar", "contacto", "correo"): (
        "📞 Con gusto. Puedes comunicarte con nosotros escribiendo al correo oficial: alcaldia@riberalta.gob.bo "
        "o aproximándote a nuestras ventanillas de atención central."
    ),
    ("gracias", "muchas gracias", "perfecto", "buenisimo"): (
        "🙏 ¡De nada, pariente! Estamos para servir a nuestra población. ¿Hay algo más en lo que pueda ayudarte?"
    ),
    ("adiós", "chau", "hasta luego", "bye"): (
        "👋 ¡Hasta pronto! Que tengas un excelente día en nuestra hermosa Riberalta. Recuerda que la plataforma municipal "
        "está siempre disponible para ti."
    ),
}

# 4. CONTEXTO INSTITUCIONAL EXCLUSIVO PARA LA IA (Sección "Quiénes somos" y Datos)
CONTEXTO_WEB = """
Información sobre esta plataforma web de Riberalta:
- Motivo de creación: Esta plataforma web fue desarrollada formalmente con el objetivo clave de reactivar el turismo local, digitalizar el acceso a la información pública municipal y conectar de manera directa y moderna a los ciudadanos con la gestión de la alcaldía.
- Visión: Convertir a Riberalta en un referente de transparencia, modernización y promoción digital en toda la región amazónica de Bolivia.
- Desarrollo: Diseñado y optimizado con un enfoque multimedia y de desarrollo web eficiente por el equipo técnico regional.

Datos Operativos del Municipio:
- Horarios de atención: Atendemos de lunes a viernes de 08:00 a 12:00 por la mañana, y de 14:00 a 18:00 por la tarde.
- Ubicación/Dirección: La alcaldía central se encuentra ubicada frente a la Plaza Principal de Riberalta.
- Contacto y teléfono: Pueden comunicarse al correo oficial alcaldia@riberalta.gob.bo o aproximarse a ventanillas de atención central.
"""

def obtener_respuesta_hibrida(mensaje_usuario: str, idioma: str = 'es') -> str:
    msg_min = mensaje_usuario.lower()
    
    # Mapeo de códigos a nombres completos de idiomas
    mapa_idiomas = {
        'es': 'Español',
        'en': 'Inglés',
        'fr': 'Francés',
        'it': 'Italiano',
        'zh': 'Chino Mandarín',
        'ja': 'Japonés'
    }
    idioma_nombre = mapa_idiomas.get(idioma.lower(), 'Español')
    
    # PASO A: Verificar si coincide con alguna palabra clave local (Costo 0) - SOLO si el idioma es español
    if idioma == 'es':
        for claves, respuesta_fija in RESPUESTAS_LOCALES.items():
            if any(c in msg_min for c in claves):
                return respuesta_fija
            
    # Obtener fecha y hora actuales para que el bot tenga contexto del tiempo
    fecha_actual = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
    
    # Construcción de la instrucción de idioma
    if idioma == 'es':
        instruccion_idioma = "Tu tono debe ser cálido, entusiasta y cercano, utilizando sutilmente expresiones locales de la amazonía boliviana (como 'pariente', 'con gusto', 'claro que sí'). Responde en ESPAÑOL."
    else:
        instruccion_idioma = f"CRITICAL INSTRUCTION: You MUST answer the user in {idioma_nombre} language. All your responses must be strictly translated to {idioma_nombre}. However, keep a warm and friendly tone."
    
    # PASO B: Si es una duda abierta o en otro idioma, usar LLM en Groq
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # El modelo gratuito más potente y rápido de Groq
            temperature=0.4,         # Creatividad media para poder conversar libremente
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "Eres Libélulin, el asistente virtual oficial, amigable y carismático de la web del Gobierno de Riberalta. "
                        f"Hoy es {fecha_actual}. "
                        f"{instruccion_idioma} "
                        "Si el ciudadano te pregunta sobre el motivo de la creación de la web o datos de la alcaldía, básate en esto:\n"
                        f"{CONTEXTO_WEB}\n"
                        "Eres una Inteligencia Artificial avanzada, así que SI PUEDES responder cualquier otra pregunta general, "
                        "ayudar con matemáticas, programación, historia, o cualquier tema que el usuario te consulte, como si fueras ChatGPT. "
                        "Nunca digas que no puedes responder algo solo por no ser de la alcaldía. Simplemente ayuda al usuario en lo que necesite siempre con actitud servicial."
                    )
                },
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        
        # Si la API falla, responder en el idioma solicitado si es posible (fallback básico)
        if idioma == 'en': return "Sorry, I am having trouble connecting to the server. Please try again later."
        elif idioma == 'fr': return "Désolé, j'ai des problèmes de connexion avec le serveur. Veuillez réessayer plus tard."
        return (
            "Lo siento, en este momento tengo problemas para conectar con el servidor central. "
            "Por favor, intenta de nuevo en unos instantes o contáctanos en nuestras oficinas."
        )

# ══════════════════════════════════════════════════════════════
# ENDPOINTS DE LA API FLASK
# ══════════════════════════════════════════════════════════════

@app.route("/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    data = request.get_json(silent=True)
    if not data or "mensaje" not in data:
        return jsonify({"error": "Se requiere el campo 'mensaje'."}), 400

    mensaje = str(data["mensaje"]).strip()
    idioma = str(data.get("idioma", "es")).strip().lower()

    if not mensaje:
        return jsonify({"error": "El mensaje está vacío."}), 400

    # Ejecutar la lógica híbrida (Local e IA unificadas) con el idioma especificado
    respuesta = obtener_respuesta_hibrida(mensaje, idioma)

    return jsonify({"respuesta": respuesta})


@app.route("/", methods=["GET"])
def index():
    return "✅ Servidor API del chatbot municipal de Riberalta corriendo con Groq. Usa POST /chat"


if __name__ == "__main__":
    print("Chatbot API de Riberalta (Groq + Flask) iniciado correctamente.")
    print("    Escuchando en: http://127.0.0.1:5000")
    print("    Presiona Ctrl+C para detener el servidor.\n")
    app.run(debug=False, port=5000)