import pdfplumber
import re

def extraer_preguntas_de_pdf(pdf_file):
    texto_completo = ""
    
    # 1. Extracción de texto plano (sin sobrecargar memoria con estilos para bancos masivos)
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text(layout=True)
            if t:
                texto_completo += t + "\n"

    # 2. Búsqueda Global de Pauta de Corrección (El "Cerebro" del motor)
    # Busca patrones tipo: "1. A", "1-A", "1: A", "001 A", en cualquier parte del texto
    mapa_claves_finales = {}
    patron_pauta = re.compile(r'\b(\d{1,4})[\.\-\:\)]?\s*([A-D])\b', re.IGNORECASE)
    
    # Escanear específicamente líneas cortas (típico de tablas de respuestas)
    for linea in texto_completo.split('\n'):
        linea = linea.strip()
        # Si la línea tiene alta densidad de "Número-Letra", es parte de la pauta
        if len(linea) < 50 and patron_pauta.search(linea):
            matches = patron_pauta.findall(linea)
            for num, letra in matches:
                mapa_claves_finales[int(num)] = letra.upper()

    # 3. Separación de bloques de preguntas
    # Divide cuando encuentra un número seguido de punto/guion al inicio de una línea
    bloques = re.split(r'\n(?=\d{1,4}[\.\-\)]\s)', texto_completo)
    
    preguntas_parsed = []
    
    # Patrones para detectar letras de alternativas y marcas de "Correcta"
    patron_alt = re.compile(r'^[\*\-\>\s]*([A-D])[\.\-\)]\s*(.*)', re.IGNORECASE | re.DOTALL)
    patrones_correcta_inline = [
        r'\*', r'\(x\)', r'\[x\]', r'->', r'respuesta:', r'correcta:'
    ]

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
            
        # Extraer el número y el cuerpo de la pregunta
        match_num = re.match(r'^(\d{1,4})[\.\-\)]\s*(.*)', bloque, re.DOTALL)
        if not match_num:
            continue
            
        num_pregunta = int(match_num.group(1))
        cuerpo_bloque = match_num.group(2)
        
        lineas = cuerpo_bloque.split('\n')
        enunciado_lineas = []
        alternativas = []
        alt_actual = None
        
        # 4. Procesamiento línea por línea para separar enunciado de alternativas
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
                
            match_alt = patron_alt.match(linea_limpia)
            
            if match_alt:
                # Guardar la alternativa anterior si existía
                if alt_actual:
                    alternativas.append(alt_actual)
                
                letra = match_alt.group(1).upper()
                texto_alt = match_alt.group(2).strip()
                
                # Evaluar si tiene marca en línea (ej: * A) Texto )
                es_marcada = any(re.search(p, linea_limpia, re.IGNORECASE) for p in patrones_correcta_inline)
                
                alt_actual = {
                    "letra": letra,
                    "texto": texto_alt,
                    "marcada": es_marcada
                }
            else:
                # Si ya estamos leyendo alternativas, esto es una línea extra de la alternativa
                if alt_actual:
                    # Chequear si la marca correcta quedó en la línea de abajo
                    if any(re.search(p, linea_limpia, re.IGNORECASE) for p in patrones_correcta_inline):
                        alt_actual["marcada"] = True
                    else:
                        alt_actual["texto"] += " " + linea_limpia
                else:
                    enunciado_lineas.append(linea_limpia)
                    
        # Agregar la última alternativa procesada
        if alt_actual:
            alternativas.append(alt_actual)

        # 5. Conciliación de la Respuesta Correcta
        correcta_idx = None
        
        # Prioridad 1: Pauta de corrección global encontrada al inicio/final del PDF
        if num_pregunta in mapa_claves_finales:
            letra_clave = mapa_claves_finales[num_pregunta]
            for idx, alt in enumerate(alternativas):
                if alt["letra"] == letra_clave:
                    correcta_idx = idx
                    alt["marcada"] = True
                    break
                    
        # Prioridad 2: Marcas en línea (Asteriscos, flechas, etc.) si no hay pauta global
        if correcta_idx is None:
            for idx, alt in enumerate(alternativas):
                if alt["marcada"]:
                    correcta_idx = idx
                    break

        enunciado_final = " ".join(enunciado_lineas).strip()
        
        # Limpiar caracteres residuales de las alternativas
        for alt in alternativas:
            alt["texto"] = re.sub(r'^\s*[\*\-\>]\s*', '', alt["texto"])

        if enunciado_final and len(alternativas) >= 2:
            preguntas_parsed.append({
                "pregunta": enunciado_final,
                "alternativas": alternativas,
                "correcta": correcta_idx
            })

    return preguntas_parsed
