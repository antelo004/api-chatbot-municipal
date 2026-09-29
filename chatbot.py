"""
chatbot.py — Servidor Flask para el Chatbot del Municipio de Riberalta
=====================================================================
Requisitos en tu entorno aislado (.venv):
    pip install flask flask-cors flask-limiter openai python-dotenv duckduckgo-search

Arrancar:
    python chatbot.py

El servidor escucha en http://127.0.0.1:5000
Endpoint: POST /chat   →  { "mensaje": "...", "idioma": "es", "primera_vez": true }  →  { "respuesta": "..." }
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

# ══════════════════════════════════════════════════════════════
# 3. HECHOS VERIFICADOS DE RIBERALTA — El LLM DEBE usar estos datos exactos.
#    Nunca debe inventar fechas, nombres ni estadísticas sobre Riberalta.
# ══════════════════════════════════════════════════════════════
HECHOS_RIBERALTA = """
=== HECHOS VERIFICADOS DE RIBERALTA — USA SIEMPRE ESTOS DATOS, NUNCA LOS INVENTES ===

HISTORIA:
- Fecha de fundación oficial: 3 de febrero de 1894
- Nombre histórico original: "Barranca Colorada"
- Fundada estratégicamente en la confluencia de los ríos Beni y Madre de Dios
- Se consolidó como eje central durante el auge del caucho y la goma (siglo XIX-XX)
- Formalmente reconocida como municipio por el Estado boliviano en 1894

GEOGRAFÍA:
- Ubicación: confluencia de los ríos Beni y Madre de Dios
- Departamento: Beni, Bolivia
- Región: Amazonía boliviana (norte del Beni)
- Apodo: "Capital de la Amazonía Boliviana" y "Corazón de la Amazonía"

ECONOMÍA:
- Principal exportación: Castaña amazónica (Bertholletia excelsa)
- Riberalta es el primer exportador de castaña de Bolivia y del mundo
- Industria castañera es el motor económico principal
- Turismo ecológico en crecimiento

CULTURA Y PUEBLOS:
- Pueblos originarios principales: Chácobo y Cavineño
- Mezcla de tradiciones originarias con herencia colona de la época gomera
- Música, danza y artesanía local típicas de la Amazonía

ALCALDÍA:
- Nombre oficial: Gobierno Autónomo Municipal de Riberalta (GAMR)
- Horarios de atención: lunes a viernes 08:00–12:00 y 14:00–18:00
- Dirección: frente a la Plaza Principal de Riberalta
- Correo: alcaldia@riberalta.gob.bo

PLATAFORMA WEB:
- Objetivo: reactivar el turismo local, digitalizar el acceso a información pública
- Visión: Riberalta como referente de transparencia y modernización en la Amazonía boliviana

=== FIN DE HECHOS VERIFICADOS ===
"""

# 4. FILTRO HÍBRIDO: Respuestas locales inmediatas (Costo $0 y velocidad instantánea)
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

# ══════════════════════════════════════════════════════════════
# 5. BÚSQUEDA WEB — DuckDuckGo (sin API key, gratuito)
# ══════════════════════════════════════════════════════════════

# Palabras clave que indican que la consulta necesita información en tiempo real
PALABRAS_BUSQUEDA = [
    # Clima y meteorología
    "clima", "tiempo", "temperatura", "lluvia", "llueve", "calor", "frío",
    "weather", "forecast", "pronóstico", "humedad", "viento",
    # Noticias y actualidad
    "noticia", "noticias", "ahora", "actual", "último", "últimas",
    "news", "latest", "today", "reciente", "novedad",
    # Preguntas factuales dinámicas
    "precio", "cotización", "dólar", "boliviano", "tipo de cambio",
    "partido", "resultado", "score", "marcador",
    "quién es el presidente", "elección", "elecciones",
    # Búsqueda explícita
    "busca", "buscar", "busque", "encuentra", "google",
    # Eventos
    "evento", "próxima", "próximo",
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
                region="es-bo",
                safesearch="moderate",
                max_results=max_resultados
            ))

        if not resultados:
            with DDGS() as ddgs:
                resultados = list(ddgs.text(
                    query,
                    safesearch="moderate",
                    max_results=max_resultados
                ))

        if not resultados:
            return ""

        texto = "📡 Información encontrada en internet:\n\n"
        for i, r in enumerate(resultados, 1):
            titulo = r.get("title", "").strip()
            cuerpo = r.get("body", "").strip()
            if titulo and cuerpo:
                texto += f"{i}. **{titulo}**\n   {cuerpo[:300]}\n\n"

        return texto.strip()

    except ImportError:
        return ""
    except Exception as e:
        print(f"[WARN] búsqueda web falló: {e}")
        return ""


def obtener_respuesta_hibrida(mensaje_usuario: str, idioma: str = 'es', primera_vez: bool = False) -> str:
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

    # PASO A: Respuestas locales inmediatas — solo español, solo si no requiere búsqueda web
    if idioma == 'es' and not necesita_busqueda_web(msg_min):
        for claves, respuesta_fija in RESPUESTAS_LOCALES.items():
            if any(c in msg_min for c in claves):
                return respuesta_fija

    # Obtener fecha y hora actuales (zona Bolivia)
    fecha_actual = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")

    # PASO B: Búsqueda web en tiempo real si la consulta lo requiere
    contexto_web_en_vivo = ""
    if necesita_busqueda_web(msg_min):
        query = mensaje_usuario
        if any(p in msg_min for p in ["clima", "tiempo", "temperatura", "lluvia", "weather", "pronóstico"]):
            if "riberalta" not in msg_min and "bolivia" not in msg_min:
                query = f"{mensaje_usuario} Riberalta Bolivia"
        contexto_web_en_vivo = buscar_en_web(query)

    # Instrucción de idioma
    if idioma == 'es':
        instruccion_idioma = (
            "Tu tono debe ser cálido y cercano, usando sutilmente expresiones locales amazónicas "
            "(como 'pariente', 'con gusto', 'claro que sí'). Responde en ESPAÑOL."
        )
    else:
        instruccion_idioma = (
            f"CRITICAL INSTRUCTION: You MUST answer the user in {idioma_nombre} language. "
            f"All your responses must be strictly in {idioma_nombre}. Keep a warm and friendly tone."
        )

    # Instrucción sobre el saludo: solo saludar en el primer mensaje de la sesión
    if primera_vez:
        instruccion_saludo = (
            "Este es el PRIMER mensaje del usuario en esta sesión. "
            "Puedes incluir un saludo breve y cálido al inicio de tu respuesta."
        )
    else:
        instruccion_saludo = (
            "IMPORTANTE: El usuario YA FUE SALUDADO al inicio de la conversación. "
            "NO empieces tu respuesta con saludos como '¡Hola!', '¡Hola pariente!', "
            "'¡Claro que sí!', 'Qué gusto saludarte', ni nada similar. "
            "Ve DIRECTO al contenido de la respuesta sin preámbulos de saludo."
        )

    # Construir el system prompt completo
    system_content = (
        "Eres Libélulin, el asistente virtual oficial de la web del Gobierno Autónomo Municipal de Riberalta. "
        f"Hoy es {fecha_actual}. "
        f"{instruccion_idioma} "
        f"{instruccion_saludo} "
        "\n\nREGLA CRÍTICA DE PRECISIÓN FACTUAL: "
        "Si el usuario pregunta sobre datos de Riberalta (historia, fundación, geografía, economía, etc.), "
        "DEBES usar EXCLUSIVAMENTE los datos del bloque siguiente. "
        "NUNCA inventes fechas, nombres o estadísticas. Si no está en el bloque, di que no tienes esa información exacta:\n"
        f"{HECHOS_RIBERALTA}\n"
        "Eres también un tutor educativo avanzado: puedes ayudar con matemáticas, ciencias, programación, "
        "historia, redacción y cualquier tema académico. Nunca digas que no puedes responder algo. "
        "Ayuda con entusiasmo, claridad y actitud servicial."
    )

    # Si hay resultados web en tiempo real, añadirlos
    if contexto_web_en_vivo:
        system_content += (
            "\n\n--- BÚSQUEDA WEB EN TIEMPO REAL ---\n"
            "El sistema realizó una búsqueda en internet. Usa la siguiente información actualizada "
            "para dar una respuesta precisa. Menciona que proviene de internet si es relevante:\n\n"
            f"{contexto_web_en_vivo}\n"
            "--- FIN DE RESULTADOS ---"
        )

    # PASO C: Llamar al LLM en Groq
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
                temperature=0.35,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": mensaje_usuario}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            ultimo_error = e
            continue

    # Fallback si todos los modelos fallan
    if ultimo_error:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

    if idioma == 'en':
        return "Sorry, I'm having trouble connecting to the server. Please try again later."
    elif idioma == 'fr':
        return "Désolé, j'ai des problèmes de connexion. Veuillez réessayer plus tard."
    return (
        "Lo siento, en este momento tengo problemas para conectar con el servidor. "
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
    # primera_vez: true solo en el primer mensaje de la sesión (enviado desde el frontend)
    primera_vez = bool(data.get("primera_vez", False))

    if not mensaje:
        return jsonify({"error": "El mensaje está vacío."}), 400

    respuesta = obtener_respuesta_hibrida(mensaje, idioma, primera_vez)
    return jsonify({"respuesta": respuesta})


@app.route("/", methods=["GET"])
def index():
    return "✅ Chatbot municipal de Riberalta (Groq + DuckDuckGo). Usa POST /chat"


if __name__ == "__main__":
    print("Chatbot API de Riberalta iniciado.")
    print("    Escuchando en: http://127.0.0.1:5000")
    print("    Presiona Ctrl+C para detener.\n")
    app.run(debug=False, port=5000)