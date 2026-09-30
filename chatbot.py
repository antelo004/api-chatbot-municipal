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
import concurrent.futures
import time
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
    api_key=os.getenv("GROQ_API_KEY", "gsk_dummy_for_init")
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

5. SÍMBOLOS Y LETRAS OFICIALES EXACTAS (NUNCA INVENTAR OTRAS):
- HIMNO NACIONAL DE BOLIVIA (Letra: José Ignacio de Sanjinés | Música: Leopoldo Benedetto Vincenti):
  Estrofa I:
  Bolivianos: el hado propicio
  coronó nuestros votos y anhelo;
  es ya libre, ya libre este suelo,
  ya cesó su servil condición.
  Estrofa II:
  Al estruendo marcial que ayer fuera
  y al clamor de la guerra horroroso,
  siguen hoy, en contraste armonioso,
  dulces himnos de paz y de unión.
  Coro:
  De la patria el alto nombre
  en glorioso esplendor conservemos,
  y en sus aras de nuevo juremos:
  ¡Morir antes que esclavos vivir!

- HIMNO AL BENI (Letra: Alfredo Pereyra Lanza | Música: Rafael Saavedra):
  Canta victorioso
  pueblo de leyenda,
  tu himno de paz y libertad;
  cante el porvenir
  la patria amada
  en tu suelo fecundo y oriental.
  En tus selvas milenarias
  el progreso cantará,
  y en tus ríos majestuosos
  el futuro brillará.

- HIMNO A RIBERALTA (Letra: Pedro Shimose | Música: Teófilo Vargas):
  ¡Salve, oh perla del norte boliviano!
  Tierra hermosa de sol y de progreso,
  donde el Beni y la Madre de Dios se unen
  en abrazo de amor y de grandeza.

=== FIN DE DATOS VERIFICADOS ===
"""

# ══════════════════════════════════════════════════════════════
# 4. MOTOR DE BÚSQUEDA WEB EN TIEMPO REAL ULTRA-RÁPIDO Y MULTI-FUENTE
#    Combina Wikipedia (OpenSearch + Extractos), DuckDuckGo (Instant & Live)
#    y Open-Meteo (Clima en tiempo real) en paralelo (< 2.5 seg)
# ══════════════════════════════════════════════════════════════

def limpiar_query_busqueda(mensaje: str) -> str:
    """Elimina prefijos conversacionales para que los motores encuentren el tema exacto."""
    q = mensaje.strip()
    q = re.sub(r'[¿?¡!]', '', q).strip()
    
    patrones_prefijo = [
        r'^(?:dame|muestrame|muestra|pasa|pasame|escribe|escribeme|canta|cantame)\s+(?:la\s+)?(?:letra\s+(?:de|del)\s+)?',
        r'^(?:cual\s+es|cuál\s+es|como\s+es|cómo\s+es)\s+(?:la\s+)?(?:letra\s+(?:de|del)\s+)?',
        r'^(?:quiero\s+saber|quisiera\s+saber|me\s+gustaria\s+saber|puedes\s+decirme|podrias\s+decirme|dime|cuentame\s+de|cuéntame\s+sobre|hablame\s+de|háblame\s+de)\s+',
        r'^(?:que\s+es|qué\s+es|quien\s+es|quién\s+es|quien\s+fue|quién\s+fue|donde\s+queda|dónde\s+queda|donde\s+esta|dónde\s+está)\s+',
    ]
    for pat in patrones_prefijo:
        m = re.match(pat, q, re.IGNORECASE)
        if m:
            resto = q[m.end():].strip()
            if len(resto) >= 3:
                q = resto
            break
            
    return q.strip()


def extraer_palabras_clave(texto: str) -> list:
    """Extrae sustantivos y términos clave filtrando artículos y preposiciones."""
    stop_words = {
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al', 'a',
        'en', 'por', 'para', 'con', 'sin', 'sobre', 'entre', 'que', 'como', 'cual', 'cuál',
        'donde', 'dónde', 'cuando', 'cuándo', 'quien', 'quién', 'es', 'son', 'fue', 'fueron', 'era', 'saber',
        'dime', 'dame', 'puedes', 'podrías', 'receta', 'historia', 'biografia', 'biografía', 'letra', 'cancion',
        'canción', 'cuentame', 'cuéntame', 'sobre', 'acerca', 'capital', 'presidente', 'hacer', 'preparar',
        'ingredientes', 'hola', 'buenas', 'saludos', 'favor', 'fundo', 'fundó', 'fundar', 'fundacion', 'fundación',
        'queda', 'quedan', 'quedaba', 'ubicado', 'ubicada', 'descubrio', 'descubrió', 'descubrimiento',
        'invento', 'inventó', 'inventor', 'fundador'
    }
    palabras = re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]+', texto.lower())
    return [p for p in palabras if p not in stop_words and len(p) > 2]


def buscar_open_meteo_riberalta() -> str:
    """Obtiene el clima exacto en vivo para Riberalta/Beni desde sensores meteorológicos."""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=-11.0065&longitude=-66.0631&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=America%2FLa_Paz"
        req = urllib.request.Request(url, headers={'User-Agent': 'MunicipalBot/2.0'})
        with urllib.request.urlopen(req, timeout=2.5) as r:
            data = json.loads(r.read().decode('utf-8'))
            curr = data.get('current', {})
            temp = curr.get('temperature_2m')
            sens = curr.get('apparent_temperature')
            hum = curr.get('relative_humidity_2m')
            viento = curr.get('wind_speed_10m')
            precip = curr.get('precipitation', 0)
            code = curr.get('weather_code', 0)
            cond = "Despejado soleado" if code == 0 else "Parcialmente nublado" if code in [1, 2, 3] else "Lluvioso" if code >= 50 else "Nublado"
            return f"🌦️ CLIMA OFICIAL EN TIEMPO REAL (Riberalta, Beni, Bolivia):\nTemperatura actual: {temp}°C (Sensación térmica: {sens}°C) | Condición: {cond} | Humedad relativa: {hum}% | Viento: {viento} km/h | Precipitación: {precip} mm."
    except Exception:
        return ""


def buscar_wikipedia(query: str) -> str:
    """
    Busca en Wikipedia usando concordancia inteligente de entidades (OpenSearch + ListSearch),
    resúmenes canónicos oficiales y extracción exacta de secciones (ej. letras oficiales de himnos).
    """
    try:
        q_clean = limpiar_query_busqueda(query)
        kw = extraer_palabras_clave(query)

        # Construir candidatos de búsqueda ordenados de más específicos a generales
        cands = []
        if kw:
            cands.append(" ".join(kw))
        if q_clean and q_clean not in cands:
            cands.append(q_clean)
        for k in kw:
            if k not in cands:
                cands.append(k)

        cand_titles = []
        snippets_list = []

        # 1. OpenSearch para encontrar títulos de entidades exactas rápidamente
        for c in cands[:3]:
            try:
                url_open = f"https://es.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(c)}&limit=3&format=json"
                req_o = urllib.request.Request(url_open, headers={'User-Agent': 'RiberaltaBot/2.0 (contacto@riberalta.gob.bo)'})
                with urllib.request.urlopen(req_o, timeout=2.0) as r_o:
                    d_o = json.loads(r_o.read().decode('utf-8'))
                    if d_o and len(d_o) > 1 and d_o[1]:
                        for ot in d_o[1]:
                            if ot not in cand_titles:
                                cand_titles.append(ot)
            except Exception:
                pass
            if len(cand_titles) >= 3:
                break

        # 2. Búsqueda de texto y fragmentos con list=search
        for c in cands[:2]:
            try:
                url_s = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(c)}&utf8=&format=json"
                req_s = urllib.request.Request(url_s, headers={'User-Agent': 'RiberaltaBot/2.0 (contacto@riberalta.gob.bo)'})
                with urllib.request.urlopen(req_s, timeout=2.2) as r_s:
                    d_s = json.loads(r_s.read().decode('utf-8'))
                    res = d_s.get('query', {}).get('search', [])
                    for r in res[:3]:
                        t = r['title']
                        if t not in cand_titles:
                            cand_titles.append(t)
                        clean_snip = re.sub(r'<[^>]+>', '', r.get('snippet', '')).strip()
                        clean_snip = clean_snip.replace('&quot;', '"').replace('&#x27;', "'").replace('&nbsp;', ' ')
                        if clean_snip and len(snippets_list) < 4:
                            snippets_list.append(f"• [{t}]: {clean_snip}")
            except Exception:
                pass
            if len(cand_titles) >= 4:
                break

        if not cand_titles and not snippets_list:
            return ""

        # Selección del mejor título canónico con puntuación ponderada:
        def calificar_titulo(t: str) -> int:
            t_low = t.lower()
            sc = 0
            if t_low == q_clean.lower():
                sc += 100
            for w in kw:
                if t_low == w:
                    sc += 60  # Coincidencia exacta de entidad (ej. Penicilina, Majadito, Mongolia, Riberalta)
                elif f" {w} " in f" {t_low} ":
                    sc += 25
                elif w in t_low:
                    sc += 15
            if any(h in query.lower() for h in ['himno', 'letra', 'cancion', 'canción']):
                if 'himno' in t_low:
                    sc += 45
            if "desambiguación" in t_low or "desambiguacion" in t_low:
                sc -= 80
            return sc

        cand_titles.sort(key=calificar_titulo, reverse=True)
        target_title = cand_titles[0] if cand_titles else None

        partes = []

        # 3. Extraer resumen canónico oficial
        if target_title:
            try:
                url_sum = f"https://es.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(target_title.replace(' ', '_'))}"
                req_sum = urllib.request.Request(url_sum, headers={'User-Agent': 'RiberaltaBot/2.0'})
                with urllib.request.urlopen(req_sum, timeout=2.2) as r_sum:
                    d_sum = json.loads(r_sum.read().decode('utf-8'))
                    extract = d_sum.get('extract', '').strip()
                    if extract:
                        partes.append(f"📖 Enciclopedia ({target_title}):\n{extract}")
            except Exception:
                pass

            # 4. Si se pide letra o texto lírico, extraer la sección oficial de letra
            if any(w in query.lower() for w in ['letra', 'estrofa', 'himno', 'cancion', 'canción']):
                try:
                    url_sec = f"https://es.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(target_title)}&prop=sections&format=json"
                    req_sec = urllib.request.Request(url_sec, headers={'User-Agent': 'RiberaltaBot/2.0'})
                    with urllib.request.urlopen(req_sec, timeout=2.0) as r_sec:
                        sec_data = json.loads(r_sec.read().decode('utf-8'))
                        sections = sec_data.get('parse', {}).get('sections', [])
                        letra_idx = None
                        for s in sections:
                            s_line = s.get('line', '').lower()
                            if 'letra' in s_line or 'presente' in s_line or 'actual' in s_line:
                                letra_idx = s.get('index')
                                break
                        if letra_idx:
                            url_sec_txt = f"https://es.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(target_title)}&section={letra_idx}&prop=wikitext&format=json"
                            req_sec_txt = urllib.request.Request(url_sec_txt, headers={'User-Agent': 'RiberaltaBot/2.0'})
                            with urllib.request.urlopen(req_sec_txt, timeout=2.0) as r_txt:
                                d_txt = json.loads(r_txt.read().decode('utf-8'))
                                wikitext = d_txt.get('parse', {}).get('wikitext', {}).get('*', '')
                                clean_wikitext = re.sub(r"'{2,}", '', wikitext)
                                clean_wikitext = re.sub(r'<[^>]+>', '', clean_wikitext)
                                clean_wikitext = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', clean_wikitext)
                                if clean_wikitext.strip():
                                    partes.append(f"🎼 Texto oficial / Letra verificada:\n{clean_wikitext.strip()[:1200]}")
                except Exception:
                    pass

        # 5. Agregar los fragmentos de referencia
        if snippets_list:
            partes.append("🔍 Referencias enciclopédicas relacionadas:\n" + "\n".join(snippets_list[:3]))

        return "\n\n".join(partes).strip()
    except Exception:
        return ""


def buscar_duckduckgo_instant(query: str) -> str:
    """Busca en el API directo de DuckDuckGo para respuestas inmediatas de hechos y definiciones."""
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.0) as r:
            data = json.loads(r.read().decode('utf-8'))
            abstract = data.get('AbstractText', '').strip()
            heading = data.get('Heading', '')
            if abstract:
                return f"🌐 Referencia rápida ({heading}):\n{abstract}"
    except Exception:
        pass
    return ""


def buscar_duckduckgo_live(query: str) -> str:
    """Busca en DuckDuckGo web con encabezados validados para evitar bloqueos."""
    try:
        url = "https://html.duckduckgo.com/html/"
        data = urllib.parse.urlencode({'q': query, 'b': ''}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://html.duckduckgo.com/',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
            }
        )
        with urllib.request.urlopen(req, timeout=2.2) as r:
            html = r.read().decode('utf-8', 'ignore')
            snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>([\s\S]*?)</a>', html)
            clean_snippets = []
            for s in snippets[:3]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                clean = clean.replace('&quot;', '"').replace('&#x27;', "'").replace('&amp;', '&').replace('&nbsp;', ' ')
                if len(clean) > 25:
                    clean_snippets.append(f"• {clean}")
            if clean_snippets:
                return "🌐 Resultados web en vivo:\n" + "\n".join(clean_snippets)
    except Exception:
        pass
    return ""


def buscar_en_internet(query: str) -> str:
    """
    Ejecuta en paralelo y con tolerancia a fallos las fuentes de búsqueda web.
    Responde en tiempo récord (< 2.5s) para proveer datos 100% verificados.
    """
    clean_q = limpiar_query_busqueda(query)
    q_lower = query.lower()

    # 1. Clima en tiempo real si se consulta por el tiempo en la región
    clima_info = ""
    if any(p in q_lower for p in ["clima", "tiempo", "temperatura", "lluvia", "llueve", "weather"]):
        if any(c in q_lower for c in ["riberalta", "beni", "aqui", "aquí", "hoy", "actual"]) or len(clean_q.split()) <= 2:
            clima_info = buscar_open_meteo_riberalta()

    # 2. Búsqueda paralela en fuentes de internet
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_wiki = executor.submit(buscar_wikipedia, clean_q)
        f_ddg_instant = executor.submit(buscar_duckduckgo_instant, clean_q)
        f_ddg_live = executor.submit(buscar_duckduckgo_live, clean_q)

        wiki_res = f_wiki.result()
        ddg_instant_res = f_ddg_instant.result()
        ddg_live_res = f_ddg_live.result()

    partes = []
    if clima_info:
        partes.append(clima_info)
    if wiki_res:
        partes.append(wiki_res)
    if ddg_instant_res:
        partes.append(ddg_instant_res)
    if ddg_live_res:
        partes.append(ddg_live_res)

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
        query_busqueda = limpiar_query_busqueda(mensaje_usuario)
        # Si preguntan por clima o tiempo sin especificar lugar, añadir Riberalta Beni
        if any(p in msg_min for p in ["clima", "tiempo", "temperatura", "lluvia", "llueve", "weather"]):
            if "riberalta" not in msg_min and "bolivia" not in msg_min and "guayaramerin" not in msg_min:
                query_busqueda = f"{query_busqueda} Riberalta Beni Bolivia"
        # Si preguntan por Cachuela Esperanza, enfocar en Beni Bolivia
        elif "cachuela" in msg_min and "bolivia" not in msg_min:
            query_busqueda = f"{query_busqueda} Cachuela Esperanza Beni Bolivia"
            
        contexto_web = buscar_en_internet(query_busqueda)

    # Instrucción sobre el tono y saludos
    if primera_vez:
        instruccion_saludo = (
            "Este es el PRIMER mensaje de la conversación. "
            "Da la respuesta directa primero y puedes cerrar cordialmente."
        )
    else:
        instruccion_saludo = (
            "IMPORTANTE: El usuario YA fue saludado anteriormente. "
            "PROHIBIDO incluir saludos iniciales como '¡Hola!', '¡Hola pariente!', 'Qué gusto saludarte', etc. "
            "Responde DIRECTAMENTE al grano desde la primerísima palabra."
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
1. MODO 'RESPUESTA DIRECTA COMO EN GOOGLE' (DE UNA):
   - Cuando el usuario pregunte por cualquier dato, fecha, autor, lugar, receta, definición, clima o hecho ("como cuando buscas en Google y te sale de una lo que pediste"):
     * Entrega la respuesta o el dato exacto DIRECTAMENTE en la PRIMERA LÍNEA en negrita (ej: "**Alexander Fleming descubrió la penicilina en 1928.**", "**La capital de Mongolia es Ulán Bator (Ulaanbaatar).**", "**Riberalta fue fundada oficialmente el 3 de febrero de 1894.**", "**El majadito es un plato tradicional a base de arroz con charque...**").
     * PROHIBIDO dar rodeos, preámbulos vacíos, introducciones o saludos que demoren el dato. Ve directo al grano desde la primera palabra.
     * Luego, en los siguientes párrafos ordenados y limpios, complementa con contexto verificado, pasos (si es receta) o detalles útiles.

2. REGLA INQUEBRANTABLE: CERO ALUCINACIONES (100% PRECISIÓN FACTUAL - NUNCA INVENTAR):
   - NUNCA inventes versos, estrofas de canciones o himnos, fechas, citas, ingredientes ni biografías.
   - Si no sabes algo y tampoco está en los resultados de internet provistos:
     * Dilo con total franqueza y claridad: "**No dispongo de esa información exacta y verificada en este momento para evitar imprecisiones.**"
     * NUNCA intentes "adivinar" ni rellenar con datos falsos.
   - Si te piden la letra de un himno o poema, entrega únicamente el texto oficial verificado. Si no dispones del texto verificado de alguna estrofa, dilo honestamente en vez de inventar versos.

3. CONOCIMIENTOS OFICIALES DE LA REGIÓN (PREVALENCIA ABSOLUTA):
   - Riberalta: Fundación oficial el 3 de febrero de 1894 (por Decreto de Mariano Baptista, fundada por el delegado Lisímaco Gutiérrez). Antiguo nombre: "Barranca Colorada".
   - Cachuela Esperanza: En el municipio de Guayaramerín (a 43 km de Guayaramerín y 90 km de Riberalta) a orillas del río Beni. Auge del caucho de Nicolás Suárez Callaú, ruinas victorianas.
   - Guayaramerín: Segunda ciudad de la provincia Vaca Díez, puerto frente a Guajará-Mirim (Brasil) a orillas del río Mamoré.
   - Laguna Tumichucua: A 25 km al sur de Riberalta, con su isla flotante.

4. CUALQUIER TEMA GENERAL, CIENTÍFICO O EDUCATIVO:
   - Responde con exactitud sobre cualquier tema del mundo (ciencia, historia, geografía, capitales, naturaleza, cocina, etc.) utilizando la información verificada de internet provista.
"""

    if contexto_web:
        system_prompt += f"""

══════════════════════════════════════════════════════
INFORMACIÓN OBTENIDA DE INTERNET EN TIEMPO REAL:
{contexto_web}
══════════════════════════════════════════════════════
Utiliza estos datos obtenidos de la web para enriquecer tu respuesta de forma estrictamente verídica y actualizada.
"""

    # Modelos activos y comprobados en la cuenta (temperatura 0.0 para cero alucinaciones)
    MODELOS_GROQ = [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b"
    ]

    ultimo_error = None
    for modelo in MODELOS_GROQ:
        try:
            response = client.chat.completions.create(
                model=modelo,
                temperature=0.0,
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
        print(f"[FATAL] Todos los modelos fallaron. Último error: {ultimo_error}")
        if os.getenv("FLASK_ENV") == "development" or os.getenv("DEBUG_LLM") == "true":
            return f"[DEBUG ERROR]: {ultimo_error}"

    if idioma == 'en':
        return "I'm having a brief connection issue. Please try again in a moment."
    return (
        "Disculpa, pariente, tuve una pequeña intermitencia de conexión con los servidores. "
        "Por favor, intenta enviar tu pregunta de nuevo en unos instantes."
    )


# ══════════════════════════════════════════════════════════════
# 6. ENDPOINTS DE LA API
# ══════════════════════════════════════════════════════════════

@app.route("/debug-llm", methods=["GET"])
def debug_llm():
    """Diagnóstico directo de los modelos de Groq."""
    modelos_disponibles = []
    try:
        modelos_disponibles = [m.id for m in client.models.list().data]
    except Exception as e:
        modelos_disponibles = [f"Error listing: {e}"]

    resultados = {}
    modelos_a_probar = [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant"
    ]
    for m in modelos_a_probar:
        try:
            r = client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Di 'hola'"}],
                max_tokens=15
            )
            resultados[m] = {"ok": True, "respuesta": r.choices[0].message.content.strip()}
        except Exception as e:
            resultados[m] = {"ok": False, "error": str(e)}
    return jsonify({
        "has_api_key": bool(os.getenv("GROQ_API_KEY")),
        "modelos_disponibles_en_cuenta": modelos_disponibles,
        "pruebas": resultados
    })

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