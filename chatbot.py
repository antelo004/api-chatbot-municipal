"""
chatbot.py — Servidor Flask para el Chatbot del Municipio de Riberalta
=====================================================================
Chatbot con acceso REAL a internet (Wikipedia + DuckDuckGo),
base de conocimiento regional verificada (Riberalta, Cachuela Esperanza, Guayaramerín)
y modelos LLM en la nube de Groq.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from openai import OpenAI
import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime

# 1. Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# CORS abierto para desarrollo y sitios autorizados
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
CORS(app, origins=allowed_origins)

# Rate limiting: 60 peticiones por minuto por IP
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# 2. Cliente Groq
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

# ══════════════════════════════════════════════════════════════
# 3. BASE DE DATOS REGIONAL VERIFICADA (Riberalta, Cachuela Esperanza, Guayaramerín)
# ══════════════════════════════════════════════════════════════
HECHOS_RIBERALTA_Y_REGION = """
=== DATOS OFICIALES Y VERIFICADOS DE RIBERALTA Y LA REGIÓN NORTE AMAZÓNICA ===

1. RIBERALTA:
- Fecha de fundación oficial: 3 de febrero de 1894 (por Decreto Supremo durante la presidencia de Mariano Baptista, fundada por el delegado nacional Lisímaco Gutiérrez).
- Nombre histórico anterior: "Barranca Colorada" (nombre dado por los navegantes que avistaron los barrancos rojizos en la orilla).
- Ubicación: Confluencia estratégica de los ríos Beni y Madre de Dios, provincia Vaca Díez, departamento del Beni, Bolivia.
- Apodo: "Capital de la Amazonía Boliviana" y "Capital Mundial de la Castaña".
- Economía: Primer exportador de castaña amazónica (nuez de la Amazonía / Bertholletia excelsa) de Bolivia y del mundo. También destaca por el ecoturismo, la madera sostenible y el comercio.
- Pueblos indígenas originarios: Chácobo, Cavineño, Tacana y Esse Ejja.
- Alcaldía: Gobierno Autónomo Municipal de Riberalta (GAMR). Horarios: Lunes a viernes 08:00–12:00 y 14:00–18:00 frente a la Plaza Principal 3 de Febrero. Correo: alcaldia@riberalta.gob.bo.

2. CACHUELA ESPERANZA:
- Ubicación: A orillas del río Beni, a unos 43 km de la ciudad de Guayaramerín y a unos 90 km de Riberalta, en el municipio de Guayaramerín, provincia Vaca Díez, departamento del Beni.
- Significado del nombre: "Cachuela" significa rápidos o caídas de agua rocosas en el río.
- Historia y Auge: A finales del siglo XIX y principios del XX, fue la capital del gigantesco imperio gomero de Nicolás Suárez Callaú ("el Rey de la Goma").
- Adelantos históricos sorprendentes: En plena selva amazónica, Cachuela Esperanza llegó a tener comodidades adelantadas a su época: el primer equipo de rayos X de Bolivia, su propio ferrocarril, cine/teatro con artistas traídos de Europa, energía eléctrica, telégrafo, imprenta y hospital de alta gama.
- Atractivo turístico actual: Destino turístico patrimonial imprescindible por sus ruinas de arquitectura victoriana inglesa, la iglesia, la casa Suárez, la vista imponente de los rápidos (cachuelas) del río Beni y su rica historia de la fiebre del caucho.

3. GUAYARAMERÍN:
- Segunda ciudad más importante de la provincia Vaca Díez (departamento del Beni).
- Ubicada a orillas del río Mamoré, en la frontera internacional frente a la ciudad brasileña de Guajará-Mirim (estado de Rondônia).
- Es un vital puerto fluvial comercial, zona franca y centro de intercambio fronterizo del norte boliviano.
- Conexión con Riberalta: Aproximadamente 85 km por carretera asfaltada (Ruta Fundamental 8).

4. LAGUNA TUMICHUCUA:
- Espectacular laguna natural ubicada a solo 25 km al sur de Riberalta.
- Famosa por albergar una isla flotante cubierta de palmeras y exuberante vegetación en su centro.
- Destino turístico favorito para paseos en bote, pesca deportiva, avistamiento de aves amazónicas, baño y leyendas tradicionales (como la del Jichi y el Bufeo).

=== FIN DE DATOS VERIFICADOS ===
"""

# ══════════════════════════════════════════════════════════════
# 4. MOTOR DE BÚSQUEDA WEB EN TIEMPO REAL (Wikipedia + DuckDuckGo)
#    No requiere API key externa, robusto y tolerante a fallos
# ══════════════════════════════════════════════════════════════

def buscar_wikipedia(query: str) -> str:
    """Busca resúmenes enciclopédicos en Wikipedia en español."""
    try:
        url_search = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
        req = urllib.request.Request(
            url_search,
            headers={"User-Agent": "RiberaltaTurismoBot/2.0 (contacto@riberalta.gob.bo)"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if not results:
                return ""
            
            titulo = results[0]["title"]
            titulo_clean = urllib.parse.quote(titulo.replace(" ", "_"))
            url_summary = f"https://es.wikipedia.org/api/rest_v1/page/summary/{titulo_clean}"
            req_sum = urllib.request.Request(
                url_summary,
                headers={"User-Agent": "RiberaltaTurismoBot/2.0 (contacto@riberalta.gob.bo)"}
            )
            with urllib.request.urlopen(req_sum, timeout=3.5) as sum_res:
                sum_data = json.loads(sum_res.read().decode("utf-8"))
                extract = sum_data.get("extract", "").strip()
                if extract:
                    return f"📖 Enciclopedia ({titulo}):\n{extract}"
    except Exception as e:
        print(f"[DEBUG] Wikipedia búsqueda no disponible para '{query}': {e}")
    return ""


def buscar_duckduckgo(query: str) -> str:
    """Busca en DuckDuckGo HTML en vivo y extrae fragmentos relevantes."""
    try:
        # Enviar petición POST a la versión HTML limpia de DuckDuckGo
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=4.5) as response:
            html = response.read().decode("utf-8", "ignore")
            snippets = []
            for m in re.finditer(r'result__snippet[^>]*>(.*?)</a>', html, re.DOTALL):
                clean = re.sub(r'<[^<]+?>', '', m.group(1)).strip()
                clean = clean.replace('&quot;', '"').replace('&#x27;', "'").replace('&amp;', '&').replace('&nbsp;', ' ')
                if clean and len(clean) > 20:
                    snippets.append(clean)
                if len(snippets) >= 3:
                    break
            
            if snippets:
                return "🌐 Resultados web en tiempo real:\n" + "\n".join(f"• {s}" for s in snippets)
    except Exception as e:
        print(f"[DEBUG] DuckDuckGo búsqueda falló para '{query}': {e}")
    
    # Intento secundario con librería ddgs si estuviera instalada y disponible
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.text(query, max_results=3))
            if res:
                textos = [f"• {r.get('body', '')}" for r in res if r.get('body')]
                if textos:
                    return "🌐 Resultados web:\n" + "\n".join(textos[:3])
    except Exception:
        pass

    return ""


def buscar_en_internet(query: str) -> str:
    """Combina Wikipedia y DuckDuckGo para obtener contexto rico y verificado."""
    partes = []
    
    # 1. Búsqueda enciclopédica
    info_wiki = buscar_wikipedia(query)
    if info_wiki:
        partes.append(info_wiki)
        
    # 2. Búsqueda web en vivo (especialmente útil para clima, noticias, detalles actuales)
    info_ddg = buscar_duckduckgo(query)
    if info_ddg:
        partes.append(info_ddg)
        
    return "\n\n".join(partes).strip()


def debe_buscar_en_web(mensaje: str) -> bool:
    """
    Determina inteligentemente si la consulta amerita búsqueda en internet.
    NO busca en internet únicamente si es un saludo puro o una despedida muy corta.
    Para cualquier pregunta sobre lugares, clima, datos, historia o turismo: SÍ BUSCA.
    """
    msg = mensaje.lower().strip()
    
    # Mensajes muy cortos que son solo saludos o cortesías
    saludos_puros = {
        "hola", "hola!", "holaa", "buen dia", "buenos dias", "buen día", 
        "buenas tardes", "buenas noches", "saludos", "hi", "hello", "hey",
        "gracias", "muchas gracias", "chau", "adios", "adiós", "hasta luego",
        "bye", "ok", "vale", "entendido", "de nada", "si", "sí", "no"
    }
    if msg in saludos_puros:
        return False
        
    # Preguntas sobre la identidad del bot
    if any(msg == p for p in ["quien eres", "quién eres", "como te llamas", "cómo te llamas", "que eres", "qué eres"]):
        return False
        
    # Para cualquier pregunta real, duda, lugar o tema: BUSCAR en la web
    return True


# ══════════════════════════════════════════════════════════════
# 5. GENERACIÓN DE RESPUESTA CON LLM
# ══════════════════════════════════════════════════════════════

def obtener_respuesta_asistente(mensaje_usuario: str, idioma: str = 'es', primera_vez: bool = False) -> str:
    msg_min = mensaje_usuario.lower().strip()

    # Mapeo de idiomas
    mapa_idiomas = {
        'es': 'Español',
        'en': 'Inglés',
        'fr': 'Francés',
        'it': 'Italiano',
        'pt': 'Portugués',
        'zh': 'Chino Mandarín',
        'ja': 'Japonés'
    }
    idioma_nombre = mapa_idiomas.get(idioma.lower(), 'Español')

    # Saludos directos e inmediatos si es exactamente un saludo
    if msg_min in ["hola", "buenas", "buen dia", "buen día", "saludos"]:
        if primera_vez:
            return (
                "¡Hola, pariente! 👋 Bienvenido a Riberalta, la Capital de la Amazonía Boliviana. "
                "Soy Libélulin, tu asistente virtual municipal y turístico. ¿Qué te gustaría conocer o consultar hoy?"
            )
        else:
            return "¿En qué más puedo colaborarte hoy, pariente?"

    if msg_min in ["gracias", "muchas gracias"]:
        return "¡Con todo el gusto del mundo, pariente! Para servirte siempre. ¿Hay algo más que quieras consultar?"

    if msg_min in ["chau", "adios", "adiós", "hasta luego", "bye"]:
        return "¡Hasta pronto, pariente! Que tengas un lindo día y disfrutes de nuestra hermosa tierra amazónica. ¡Vuelve pronto!"

    # Obtener fecha y hora actuales
    fecha_actual = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")

    # BÚSQUEDA WEB EN TIEMPO REAL si corresponde
    contexto_web = ""
    if debe_buscar_en_web(mensaje_usuario):
        query_busqueda = mensaje_usuario
        # Si preguntan por clima o tiempo sin especificar lugar, añadir Riberalta Beni
        if any(p in msg_min for p in ["clima", "tiempo", "temperatura", "lluvia", "llueve", "weather"]):
            if "riberalta" not in msg_min and "bolivia" not in msg_min and "guayaramerin" not in msg_min:
                query_busqueda = f"{mensaje_usuario} Riberalta Beni Bolivia"
        # Si preguntan por Cachuela Esperanza, enfocar en Beni Bolivia
        elif "cachuela" in msg_min and "bolivia" not in msg_min:
            query_busqueda = f"{mensaje_usuario} Cachuela Esperanza Beni Bolivia"
            
        contexto_web = buscar_en_internet(query_busqueda)

    # Instrucción sobre el tono y saludos
    if primera_vez:
        instruccion_saludo = (
            "Este es el PRIMER mensaje de la conversación. "
            "Puedes incluir un saludo breve y cordial al inicio."
        )
    else:
        instruccion_saludo = (
            "IMPORTANTE: El usuario YA fue saludado anteriormente. "
            "NO incluyas saludos iniciales como '¡Hola!', '¡Hola pariente!', 'Qué gusto saludarte', etc. "
            "Responde DIRECTAMENTE a lo preguntado."
        )

    # System prompt estructurado
    system_prompt = f"""Eres Libélulin, el asistente virtual turístico y de atención ciudadana del Gobierno Autónomo Municipal de Riberalta (Beni, Bolivia).
Fecha actual: {fecha_actual}.
Idioma de respuesta: Responde estrictamente en {idioma_nombre}.

TONO Y PERSONALIDAD:
- Eres cálido, educado, hospitalario y orgulloso de la Amazonía boliviana.
- Usa con naturalidad y sutileza expresiones benianas/amazónicas como "pariente", "con gusto", "claro que sí".
- {instruccion_saludo}

CONOCIMIENTO OFICIAL DE LA REGIÓN (USA SIEMPRE ESTOS DATOS):
{HECHOS_RIBERALTA_Y_REGION}

INSTRUCCIONES CLAVE DE RESPUESTA:
1. LUGARES Y TURISMO REGIONAL: Si te preguntan sobre Cachuela Esperanza, Guayaramerín, la Laguna Tumichucua, la castaña o Riberalta, responde con gran detalle histórico y turístico, destacando que Cachuela Esperanza queda en el municipio de Guayaramerín (a unos 43 km de Guayaramerín y 90 km de Riberalta), su relación con el magnate del caucho Nicolás Suárez, sus imponentes rápidos y su arquitectura victoriana.
2. ACCESO A INTERNET Y ACTUALIDAD: Cuentas con un motor de búsqueda web en tiempo real. Utiliza la información provista abajo para responder con total precisión, actualidad y rigor. NUNCA digas que no tienes acceso a internet o que no puedes saberlo si la información se encuentra en los resultados o en tus conocimientos.
3. CONOCIMIENTOS GENERALES Y EDUCATIVOS: Además de turismo municipal, eres un tutor versátil: puedes explicar historia, ciencias, naturaleza amazónica, redactar textos o resolver dudas con entusiasmo.
"""

    if contexto_web:
        system_prompt += f"""

══════════════════════════════════════════════════════
INFORMACIÓN OBTENIDA DE INTERNET EN TIEMPO REAL:
{contexto_web}
══════════════════════════════════════════════════════
Utiliza estos datos obtenidos de la web para enriquecer tu respuesta de forma verídica y actualizada.
"""

    # Modelos de Groq (priorizando llama-3.3-70b-versatile por su alta capacidad de razonamiento)
    MODELOS_GROQ = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]

    ultimo_error = None
    for modelo in MODELOS_GROQ:
        try:
            response = client.chat.completions.create(
                model=modelo,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": mensaje_usuario}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[WARN] Error con modelo {modelo}: {e}")
            ultimo_error = e
            continue

    if ultimo_error:
        import traceback
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

    if idioma == 'en':
        return "I'm having a brief connection issue. Please try again in a moment."
    return (
        "Disculpa, pariente, tuve una pequeña intermitencia de conexión con los servidores. "
        "Por favor, intenta enviar tu pregunta de nuevo en unos instantes."
    )


# ══════════════════════════════════════════════════════════════
# 6. ENDPOINTS DE LA API
# ══════════════════════════════════════════════════════════════

@app.route("/chat", methods=["POST"])
@limiter.limit("40 per minute")
def chat():
    data = request.get_json(silent=True)
    if not data or "mensaje" not in data:
        return jsonify({"error": "Se requiere el campo 'mensaje'."}), 400

    mensaje = str(data["mensaje"]).strip()
    idioma = str(data.get("idioma", "es")).strip().lower()
    primera_vez = bool(data.get("primera_vez", False))

    if not mensaje:
        return jsonify({"error": "El mensaje no puede estar vacío."}), 400

    respuesta = obtener_respuesta_asistente(mensaje, idioma, primera_vez)
    return jsonify({"respuesta": respuesta})


@app.route("/test-search", methods=["GET"])
def test_search_endpoint():
    """Endpoint público para verificar que la búsqueda en internet funciona activamente."""
    q = request.args.get("q", "Cachuela Esperanza Bolivia").strip()
    resultado = buscar_en_internet(q)
    return jsonify({
        "consulta": q,
        "tiene_resultados": bool(resultado),
        "longitud": len(resultado),
        "contenido": resultado
    })


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "servicio": "API Chatbot Municipal y Turístico de Riberalta",
        "motor_ia": "Groq LLaMA 3.3 70B",
        "busqueda_web": "Activa (Wikipedia + DuckDuckGo)",
        "endpoints": {
            "POST /chat": "Conversación con el chatbot",
            "GET /test-search?q=...": "Prueba directa de búsqueda en internet"
        }
    })


if __name__ == "__main__":
    print("Chatbot API de Riberalta iniciado.")
    print("Escuchando en http://127.0.0.1:5000")
    app.run(debug=False, port=5000)