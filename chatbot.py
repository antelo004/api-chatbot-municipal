"""
chatbot.py — Servidor Flask para el Chatbot del Municipio de Riberalta
=====================================================================
Requisitos en tu entorno aislado (.venv):
    pip install flask flask-cors flask-limiter openai python-dotenv duckduckgo-search

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

# ══════════════════════════════════════════════════════════════
# 5. BÚSQUEDA WEB — DuckDuckGo (sin API key, gratuito)
# ══════════════════════════════════════════════════════════════

# Palabras clave que indican que la consulta necesita información en tiempo real
PALABRAS_BUSQUEDA = [
    # Clima y meteorología
    "clima", "tiempo", "temperatura", "lluvia", "llueve", "calor", "frío",
    "weather", "forecast", "pronóstico", "humedad", "viento",
    # Noticias y actualidad
    "noticia", "noticias", "hoy", "ahora", "actual", "último", "últimas",
    "news", "latest", "today", "reciente", "novedad",
    # Preguntas factuales dinámicas
    "precio", "cotización", "dólar", "boliviano", "tipo de cambio",
    "partido", "resultado", "score", "marcador",
    "quién ganó", "quién es el presidente", "elección", "elecciones",
    # Búsqueda explícita
    "busca", "buscar", "busque", "encuentra", "google",
    # Eventos y fechas futuras
    "evento", "cuándo", "cuando es", "próxima", "próximo",
]

def necesita_busqueda_web(mensaje: str) -> bool:
    """Determina si el mensaje requiere búsqueda en internet."""
    msg_lower = mensaje.lower()
    return any(palabra in msg_lower for palabra in PALABRAS_BUSQUEDA)

def buscar_en_web(query: str, max_resultados: int = 3) -> str:
    """
    Realiza una búsqueda en DuckDuckGo y devuelve un resumen de los resultados.
    Retorna cadena vacía si falla o no hay resultados.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = list(ddgs.text(
                query,
                region="es-bo",   # Bolivia en español (fallback a global si no hay)
                safesearch="moderate",
                max_results=max_resultados
            ))
        
        if not resultados:
            # Intentar sin región específica
            with DDGS() as ddgs:
                resultados = list(ddgs.text(
                    query,
                    safesearch="moderate",
                    max_results=max_resultados
                ))
        
        if not resultados:
            return ""
        
        # Formatear los resultados para incluir en el contexto del LLM
        texto = "📡 Información encontrada en internet:\n\n"
        for i, r in enumerate(resultados, 1):
            titulo = r.get("title", "").strip()
            cuerpo = r.get("body", "").strip()
            if titulo and cuerpo:
                texto += f"{i}. **{titulo}**\n   {cuerpo[:300]}\n\n"
        
        return texto.strip()
    
    except ImportError:
        # ddgs no está instalada en este entorno
        return ""
    except Exception as e:
        # Registrar pero no romper el flujo
        print(f"[WARN] búsqueda web falló: {e}")
        return ""


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
    # Excluimos saludos si además contiene palabras de búsqueda (ej: "hola, dime el clima")
    if idioma == 'es' and not necesita_busqueda_web(msg_min):
        for claves, respuesta_fija in RESPUESTAS_LOCALES.items():
            if any(c in msg_min for c in claves):
                return respuesta_fija
        
    # Obtener fecha y hora actuales para que el bot tenga contexto del tiempo
    fecha_actual = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
    
    # PASO B: Búsqueda web si la consulta lo requiere
    contexto_web_en_vivo = ""
    if necesita_busqueda_web(msg_min):
        # Construir una query optimizada para el buscador
        query = mensaje_usuario
        # Para preguntas de clima de Riberalta sin mencionar la ciudad, agregarla
        if any(p in msg_min for p in ["clima", "tiempo", "temperatura", "lluvia", "weather", "pronóstico"]):
            if "riberalta" not in msg_min and "bolivia" not in msg_min:
                query = f"{mensaje_usuario} Riberalta Bolivia"
        
        contexto_web_en_vivo = buscar_en_web(query)
    
    # Construcción de la instrucción de idioma
    if idioma == 'es':
        instruccion_idioma = "Tu tono debe ser cálido, entusiasta y cercano, utilizando sutilmente expresiones locales de la amazonía boliviana (como 'pariente', 'con gusto', 'claro que sí'). Responde en ESPAÑOL."
    else:
        instruccion_idioma = f"CRITICAL INSTRUCTION: You MUST answer the user in {idioma_nombre} language. All your responses must be strictly translated to {idioma_nombre}. However, keep a warm and friendly tone."
    
    # Construir el mensaje de sistema con o sin contexto web en vivo
    system_content = (
        "Eres Libélulin, el asistente virtual oficial, amigable y carismático de la web del Gobierno de Riberalta. "
        f"Hoy es {fecha_actual}. "
        f"{instruccion_idioma} "
        "Si el ciudadano te pregunta sobre el motivo de la creación de la web o datos de la alcaldía, básate en esto:\n"
        f"{CONTEXTO_WEB}\n"
        "Eres un tutor educativo y una Inteligencia Artificial avanzada: SI PUEDES responder cualquier pregunta general, "
        "ayudar a escolares, universitarios y ciudadanos con tareas, matemáticas, ciencias, biología, programación, historia, "
        "redacción o cualquier tema académico o educativo que te consulten, como si fueras ChatGPT con sabiduría amazónica. "
        "Nunca digas que no puedes responder algo solo por no ser de la alcaldía. Simplemente ayuda con entusiasmo, claridad y actitud servicial."
    )
    
    # Si tenemos resultados de búsqueda, añadirlos como contexto
    if contexto_web_en_vivo:
        system_content += (
            "\n\n--- BÚSQUEDA WEB EN TIEMPO REAL ---\n"
            "El sistema realizó una búsqueda en internet para responder esta consulta. "
            "Usa la siguiente información actualizada para dar una respuesta precisa y útil. "
            "Menciona que la información proviene de internet si es relevante:\n\n"
            f"{contexto_web_en_vivo}\n"
            "--- FIN DE RESULTADOS DE BÚSQUEDA ---"
        )
    
    # PASO C: Si es una duda abierta o educativa, usar LLM en Groq con lista de modelos activos
    MODELOS = [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant"
    ]

    ultimo_error = None
    for modelo in MODELOS:
        try:
            response = client.chat.completions.create(
                model=modelo,
                temperature=0.4,
                messages=[
                    {
                        "role": "system", 
                        "content": system_content
                    },
                    {"role": "user", "content": mensaje_usuario}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            ultimo_error = e
            continue

    # Si todos los modelos fallan, registrar el error y dar respuesta de respaldo
    if ultimo_error:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
    
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