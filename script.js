document.addEventListener("DOMContentLoaded", () => {
    const chatToggle = document.getElementById("chatbot-toggle");
    const chatWindow = document.getElementById("chatbot-window");
    const chatInput = document.getElementById("chat-input");
    const chatEnviar = document.getElementById("chat-enviar");
    const chatMensajes = document.getElementById("chat-mensajes");

    // URL de tu servidor backend de IA (Ajusta el puerto si es necesario)
    const API_URL = "http://127.0.0.1:5000/chat";

    // 1. Alternar apertura y cierre de la ventana
    chatToggle.addEventListener("click", () => {
        const contenedor = document.querySelector(".chatbot-contenedor");
        chatWindow.classList.toggle("abierto");
        if (chatWindow.classList.contains("abierto")) {
            contenedor.classList.add("chat-abierto");
            chatInput.focus();
        } else {
            contenedor.classList.remove("chat-abierto");
        }
    });

    // 2. Función para enviar el mensaje
    async function enviarMensaje() {
        const texto = chatInput.value.trim();
        if (!texto) return;

        // Renderizar mensaje del usuario
        agregarBurbuja(texto, "msg-user");
        chatInput.value = "";
        ajustarInput();

        // Bloquear controles mientras la IA responde
        chatInput.disabled = true;
        chatEnviar.disabled = true;

        // Mostrar indicador de "escribiendo..."
        const indicadorEscribiendo = mostrarIndicadorEscribiendo();


        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ mensaje: texto })
            });

            if (!response.ok) {
                throw new Error("Error en la respuesta del servidor");
            }

            const data = await response.json();

            // Eliminar indicador y mostrar respuesta del bot con efecto de escritura
            indicadorEscribiendo.remove();

            const botDiv = document.createElement("div");
            botDiv.classList.add("msg", "msg-bot");
            const botText = document.createElement("span");
            botText.classList.add("bot-text");
            botDiv.appendChild(botText);
            chatMensajes.appendChild(botDiv);
            hacerScrollAlFinal();

            // Escribir la respuesta carácter a carácter
            await typeText(botText, data.respuesta, 18);

        } catch (error) {
            console.error("Error al conectar con el chatbot:", error);
            indicadorEscribiendo.remove();

            const botDivErr = document.createElement("div");
            botDivErr.classList.add("msg", "msg-bot");
            const botTextErr = document.createElement("span");
            botTextErr.classList.add("bot-text");
            botDivErr.appendChild(botTextErr);
            chatMensajes.appendChild(botDivErr);
            hacerScrollAlFinal();

            await typeText(botTextErr, "Lo siento, hubo un problema al conectar con el servidor. Por favor, intenta de nuevo más tarde.", 18);
        } finally {
            // Desbloquear controles
            chatInput.disabled = false;
            chatEnviar.disabled = false;
            chatInput.focus();
            hacerScrollAlFinal();

        }
    }

    // 3. Auxiliar para insertar las burbujas en el DOM
    function agregarBurbuja(texto, clase) {
        const div = document.createElement("div");
        div.classList.add("msg", clase);
        
        // Render bot responses using markdown-it if available
        if (clase.includes("msg-bot") && typeof markdownit === "function") {
            try {
                const md = markdownit({
                    html: true,
                    linkify: true,
                    breaks: true
                });
                div.innerHTML = md.render(texto);
            } catch (e) {
                console.error("Error al renderizar markdown:", e);
                div.textContent = texto;
            }
        } else {
            div.textContent = texto;
        }
        
        chatMensajes.appendChild(div);
        hacerScrollAlFinal();
    }

    // 4. Auxiliar para crear la burbuja de "escribiendo..."
    function mostrarIndicadorEscribiendo() {
        const div = document.createElement("div");
        div.classList.add("msg", "msg-bot", "msg-typing");
        div.innerHTML = `<span></span><span></span><span></span>`;
        chatMensajes.appendChild(div);
        hacerScrollAlFinal();
        return div;
    }

    // Función para escribir texto carácter a carácter en un elemento
    async function typeText(el, text, delay = 20) {
        el.textContent = "";
        for (let i = 0; i < text.length; i++) {
            el.textContent += text[i];
            if (i % 6 === 0) hacerScrollAlFinal();
            await new Promise(r => setTimeout(r, delay));
        }
        hacerScrollAlFinal();
    }

    // 5. Auto-scroll automático al último mensaje
    function hacerScrollAlFinal() {
        chatMensajes.scrollTo({
            top: chatMensajes.scrollHeight,
            behavior: "smooth"
        });
    }

    // 6. Auto-ajustar la altura del textarea según el texto escrito
    function ajustarInput() {
        chatInput.style.height = "auto";
        chatInput.style.height = (chatInput.scrollHeight) + "px";
    }

    // 7. Pestañas: Alcaldía (predefinidas) y Educación (entrada libre)
    const tabs = document.querySelectorAll('.chat-tab');
    const opcionesAlcaldia = document.getElementById('chat-opciones-alcaldia');
    const opcionesEducacion = document.getElementById('chat-opciones-educacion');
    const inputArea = document.querySelector('.chat-input-area');

    // Respuestas predefinidas para Alcaldía
    const alcaldiaAnswers = {
        horarios: 'Nuestra atención es de lunes a viernes de 08:00 a 16:00. Sábados solo oficina de registro de 09:00 a 12:00.',
        ubicacion: 'La Alcaldía se ubica en la Av. Beni N°123, centro de Riberalta. Puedes ver el mapa en la sección de contacto.',
        contacto: 'Teléfono: +591 3 1234567. Email: alcaldia@riberalta.gob.bo. Atención por redes sociales dentro de horario laboral.',
        tramites: 'Trámites comunes: registro civil, licencias, permisos de construcción y solicitud de certificados. Visita la sección de trámites para requisitos.'
    };

    function setMode(mode){
        tabs.forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
        if(mode === 'alcaldia'){
            if(opcionesAlcaldia) opcionesAlcaldia.classList.add('chat-opciones--visible');
            if(opcionesEducacion) opcionesEducacion.classList.remove('chat-opciones--visible');
            // desactivar input
            if(inputArea) inputArea.classList.add('chat-mode-disabled');
            chatInput.disabled = true;
            chatEnviar.disabled = true;
            chatInput.placeholder = 'Seleccione una pregunta predefinida.';
        } else {
            if(opcionesAlcaldia) opcionesAlcaldia.classList.remove('chat-opciones--visible');
            if(opcionesEducacion) opcionesEducacion.classList.add('chat-opciones--visible');
            if(inputArea) inputArea.classList.remove('chat-mode-disabled');
            chatInput.disabled = false;
            chatEnviar.disabled = false;
            chatInput.placeholder = 'Escribe tu consulta aquí...';
        }
    }

    // Inicializar
    if(tabs.length) setMode('alcaldia');
    tabs.forEach(tab => tab.addEventListener('click', () => setMode(tab.dataset.mode)));

    // Botones de Alcaldía: respuestas predefinidas
    if(opcionesAlcaldia){
        opcionesAlcaldia.querySelectorAll('.chat-opcion').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const key = btn.getAttribute('data-key');
                agregarBurbuja(btn.textContent, 'msg-user');
                const indicador = mostrarIndicadorEscribiendo();
                await new Promise(r => setTimeout(r, 600));
                indicador.remove();
                const answer = alcaldiaAnswers[key] || 'Disculpa, no tengo esa respuesta ahora.';
                const botDiv = document.createElement('div');
                botDiv.classList.add('msg', 'msg-bot');
                const botText = document.createElement('span');
                botText.classList.add('bot-text');
                botDiv.appendChild(botText);
                chatMensajes.appendChild(botDiv);
                hacerScrollAlFinal();
                await typeText(botText, answer, 16);
            });
        });
    }

    // Botones de Educación: rellenan input y envían
    if(opcionesEducacion){
        opcionesEducacion.querySelectorAll('.chat-opcion').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const pregunta = btn.getAttribute('data-pregunta');
                chatInput.value = pregunta;
                ajustarInput();
                enviarMensaje();
            });
        });
    }

    // Eventos de disparo
    chatEnviar.addEventListener("click", enviarMensaje);

    chatInput.addEventListener("input", ajustarInput);

    chatInput.addEventListener("keydown", (e) => {
        // Enviar con Enter (sin Shift para saltos de línea)
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            enviarMensaje();
        }
    });

    // 8. Efecto de Cursor Luminoso (Aura que sigue el mouse)
    const cursorGlow = document.querySelector('.cursor-glow');
    if (cursorGlow) {
        let mouseX = window.innerWidth / 2;
        let mouseY = window.innerHeight / 2;
        let glowX = mouseX;
        let glowY = mouseY;
        let isHovering = false;

        document.addEventListener('mousemove', (e) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
            
            // Mostrar el cursor glow al mover el mouse por primera vez
            if (cursorGlow.style.opacity !== '1') {
                cursorGlow.style.opacity = '1';
            }
        });

        // Loop de animación para un movimiento suave (lerp)
        function animateGlow() {
            // Factor de suavidad (0.1 = muy suave/lento, 0.5 = más rápido)
            glowX += (mouseX - glowX) * 0.15;
            glowY += (mouseY - glowY) * 0.15;
            
            cursorGlow.style.transform = `translate(${glowX}px, ${glowY}px) translate(-50%, -50%)`;
            
            requestAnimationFrame(animateGlow);
        }
        
        animateGlow();

        // Efectos extra al pasar sobre elementos clickeables
        const interactiveElements = document.querySelectorAll('a, button, input, textarea');
        interactiveElements.forEach(el => {
            el.addEventListener('mouseenter', () => {
                cursorGlow.style.width = '250px';
                cursorGlow.style.height = '250px';
                cursorGlow.style.background = 'radial-gradient(circle, rgba(197, 164, 83, 0.25) 0%, rgba(30, 82, 56, 0.1) 50%, rgba(9, 18, 12, 0) 70%)';
            });
            el.addEventListener('mouseleave', () => {
                cursorGlow.style.width = '400px';
                cursorGlow.style.height = '400px';
                cursorGlow.style.background = 'radial-gradient(circle, rgba(197, 164, 83, 0.15) 0%, rgba(30, 82, 56, 0.05) 40%, rgba(9, 18, 12, 0) 70%)';
            });
        });
    }

    // 9. Reloj y Fecha en tiempo real (Riberalta, Bolivia - BOT)
    function actualizarReloj() {
        const elFecha = document.getElementById("tiempo-fecha");
        const elHora = document.getElementById("tiempo-hora");
        if (!elFecha || !elHora) return;

        const ahora = new Date();
        
        // Obtener fecha formateada para Bolivia
        const opcionesFecha = {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "America/La_Paz"
        };
        let fechaTexto = ahora.toLocaleDateString("es-BO", opcionesFecha);
        
        // Capitalizar la primera letra del día de la semana
        fechaTexto = fechaTexto.charAt(0).toUpperCase() + fechaTexto.slice(1);

        // Obtener hora formateada para Bolivia (24 horas)
        const opcionesHora = {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
            timeZone: "America/La_Paz"
        };
        const horaTexto = ahora.toLocaleTimeString("es-BO", opcionesHora);

        elFecha.textContent = fechaTexto;
        elHora.textContent = horaTexto;
    }

    actualizarReloj();
    setInterval(actualizarReloj, 1000);
});

// ==========================================================================
// ── CONTROL DE LA PANTALLA DE CARGA (PRELOADER CINEMATOGRÁFICO)
// ==========================================================================
window.addEventListener("load", () => {
    const pantallaCarga = document.getElementById("pantalla-carga");
    if (pantallaCarga) {
        setTimeout(() => {
            pantallaCarga.classList.add("ocultar");
            document.body.classList.remove("cargando");
        }, 3500); // Retraso de 3500 ms (3.5 segundos) para garantizar el impacto cinematográfico
    }
});