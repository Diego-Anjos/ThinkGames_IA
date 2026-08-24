import json
import logging
import os
import re
import warnings

import requests

# Injeta os certificados do sistema operacional antes de carregar a IA.
# Sem isso, redes com inspeção TLS (ex.: acadêmica) quebram o handshake.
import truststore
truststore.inject_into_ssl()

# Suprime temporariamente o aviso de depreciação do pacote generativeai
# (o aviso é emitido no import e o Python atribui ao app.py, não ao módulo).
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r".*google\.generativeai.*",
)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from whitenoise import WhiteNoise

# Carrega o .env ANTES de ler as chaves
load_dotenv()

gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not gemini_key:
    raise ValueError("A chave GEMINI_API_KEY não está configurada no arquivo .env.")

# transport="rest" é obrigatório aqui: o gRPC usa o próprio armazenamento de
# certificados (BoringSSL) e ignora o truststore, então em redes com inspeção
# TLS o handshake falha e o cliente fica reconectando para sempre, sem respeitar
# o timeout. O REST passa pelo ssl do Python, onde o truststore funciona.
genai.configure(api_key=gemini_key, transport="rest")

RAWG_API_KEY = (os.getenv("RAWG_API_KEY") or "").strip()
RAWG_SEARCH_URL = "https://api.rawg.io/api/games"
GEMINI_MODEL = "gemini-3.6-flash"

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root="static/")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
app.logger.setLevel(logging.INFO)


def map_rawg_game(game):
    """Normaliza um jogo do RAWG nos campos esperados pelo frontend."""
    platforms = []
    for item in game.get("platforms") or []:
        platform_name = (item.get("platform") or {}).get("name")
        if platform_name:
            platforms.append(platform_name)

    return {
        "name": game.get("name") or "Jogo sem nome",
        "background_image": game.get("background_image") or "",
        "rating": game.get("rating") or 0,
        "released": game.get("released") or "",
        "platforms": platforms,
    }


def clean_ia_json_text(raw_text):
    """Remove as crases de markdown que a IA às vezes coloca em volta do JSON."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_games_info(raw_text, limit=6):
    """Extrai jogos com nome, estúdio, gênero e descrição a partir do JSON da IA."""
    return extract_games_info(json.loads(clean_ia_json_text(raw_text)), limit=limit)


def extract_games_info(data, limit=6):
    """Normaliza a lista de jogos já decodificada do JSON da IA."""
    if isinstance(data, dict):
        data = (
            data.get("games")
            or data.get("recommendations")
            or data.get("results")
        )
        if not isinstance(data, list):
            data = []

    games = []
    for item in data or []:
        if isinstance(item, str) and item.strip():
            games.append({
                "name": item.strip(),
                "studio": "Desconhecido",
                "genre": "Vários",
                "modes": "Não informado",
                "description": "Sem descrição.",
            })
        elif isinstance(item, dict):
            name = item.get("name") or item.get("title")
            if not name:
                continue
            games.append({
                "name": str(name).strip(),
                "studio": str(item.get("studio") or "Desconhecido").strip(),
                "genre": str(item.get("genre") or "Vários").strip(),
                "modes": _stringify_modes(item.get("modes")),
                "description": str(item.get("description") or "Sem descrição.").strip(),
            })

    if limit is None:
        return games
    return games[:limit]


def _stringify_modes(value):
    """Normaliza modos de jogo para uma string única no card."""
    if isinstance(value, list):
        modes = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(modes) if modes else "Não informado"
    text = str(value or "").strip()
    return text or "Não informado"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/suggest", methods=["POST"])
def suggest():
    rawg_key = RAWG_API_KEY or (os.getenv("RAWG_API_KEY") or "").strip()
    gemini_key_atual = (os.getenv("GEMINI_API_KEY") or "").strip()

    if not rawg_key or not gemini_key_atual:
        faltando = []
        if not rawg_key:
            faltando.append("RAWG_API_KEY")
        if not gemini_key_atual:
            faltando.append("GEMINI_API_KEY")
        erro_msg = "Falta configurar: " + ", ".join(faltando)
        app.logger.error("[ERRO FATAL] %s no arquivo .env!", erro_msg)
        return jsonify({
            "error": f"Erro de configuração do servidor: {erro_msg}"
        }), 500

    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()

    if not description:
        return jsonify({"error": "A descrição do jogo é obrigatória."}), 400

    try:
        app.logger.info("--- NOVA BUSCA INICIADA ---")
        app.logger.info("1. Pedido do usuário: '%s'", description)
        app.logger.info(
            "2. Conectando com a IA Gemini (%s, timeout de 25s)...",
            GEMINI_MODEL,
        )
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = f"""
        Você é um curador especialista em videogames e um motor de recomendação avançado.
        Analise o pedido do usuário: "{description}"

        REGRA CRÍTICA DE FORMATAÇÃO: Você está retornando um JSON. NUNCA use aspas duplas (") dentro do conteúdo das strings. Se precisar destacar algo, use aspas simples (').

        SUAS DIRETRIZES DE RECOMENDAÇÃO:
        1. Interpretação Profunda: Se o usuário citar um jogo específico (ex: "parecido com Resident Evil"), identifique a essência desse jogo (atmosfera, mecânicas, câmera, tema) e recomende outros jogos que entreguem uma experiência semelhante (mas evite recomendar exatamente o jogo que ele usou como base).
        2. Cenários e Emoções: Se o usuário descrever um cenário abstrato, sentimento ou mecânica, encontre os títulos reais que melhor representem essa vivência.
        3. Curadoria: Traga uma mistura de jogos muito aclamados e também "hidden gems" (joias escondidas) que combinem perfeitamente.
        4. Quantidade: Forneça EXATAMENTE 6 recomendações precisas na lista "games".

        Retorne APENAS um objeto JSON no seguinte formato EXATO:
        {{
            "message": "Uma mensagem amigável e entusiasmada (1 ou 2 frases, sem aspas duplas internas) falando diretamente com o usuário, comentando sobre a escolha dele e apresentando as recomendações.",
            "games": [
                {{
                    "name": "Nome original em inglês",
                    "studio": "Nome da desenvolvedora",
                    "genre": "Gênero principal",
                    "modes": "Modos de jogo",
                    "description": "Uma sinopse empolgante em PT-BR (máximo 3 linhas, sem aspas duplas internas) justificando a escolha."
                }}
            ]
        }}
        Não adicione markdown (como ```json), crases ou nenhum texto fora do JSON.
        """

        # O request_options força a queda se a rede segurar a conexão
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            request_options={"timeout": 25},
        )

        app.logger.info("3. Resposta bruta do Gemini recebida!")

        raw_text = clean_ia_json_text(response.text)
        try:
            ia_data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            app.logger.error(
                "Erro ao decodificar JSON da IA: %s. Texto recebido: %s", e, raw_text
            )
            return jsonify({
                "error": "A IA retornou um formato inválido. Tente novamente."
            }), 500

        ai_message = "Aqui estão algumas recomendações incríveis para você!"
        if isinstance(ia_data, dict):
            ai_message = str(ia_data.get("message") or ai_message).strip() or ai_message

        games_info = extract_games_info(ia_data)
        app.logger.info("4. Jogos extraídos: %s", [game.get("name") for game in games_info])

        resultados_finais = []

        app.logger.info("5. Iniciando buscas na RAWG...")
        for game in games_info:
            name = game.get("name")
            if not name:
                continue
            app.logger.info(" -> Buscando imagem para: %s", name)
            req = requests.get(
                RAWG_SEARCH_URL,
                params={
                    "key": rawg_key,
                    "search": name,
                    "page_size": 1,
                },
                timeout=10,
            )

            if req.status_code == 200:
                rawg_data = req.json()
                if rawg_data.get("results"):
                    jogo_encontrado = rawg_data["results"][0]
                    jogo_completo = map_rawg_game(jogo_encontrado)
                    jogo_completo["description"] = game.get("description", "Sem descrição.")
                    jogo_completo["genre"] = game.get("genre", "Vários")
                    jogo_completo["studio"] = game.get("studio", "Desconhecido")
                    jogo_completo["modes"] = game.get("modes", "Não informado")
                    resultados_finais.append(jogo_completo)
                    app.logger.info("    [OK] Encontrado!")
                else:
                    app.logger.warning("    [AVISO] Jogo não retornado na busca RAWG.")
            else:
                app.logger.error("    [ERRO] RAWG retornou status %s", req.status_code)

        app.logger.info("6. Busca finalizada com sucesso! Retornando ao frontend.")
        return jsonify({"ai_message": ai_message, "results": resultados_finais})

    except Exception as e:
        app.logger.error("[ERRO GRAVE] O processamento falhou: %s", e)
        app.logger.exception("Falha ao processar recomendação com Gemini/RAWG")
        return jsonify({
            "error": "Erro na comunicação com a IA ou RAWG. Tente novamente."
        }), 500


@app.route("/api/genre", methods=["GET"])
def get_by_genre():
    genre = (request.args.get("genre") or "action").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    rawg_key = RAWG_API_KEY or (os.getenv("RAWG_API_KEY") or "").strip()
    if not rawg_key:
        app.logger.error("[ERRO FATAL] RAWG_API_KEY não configurada no .env!")
        return jsonify({"error": "Erro de configuração do servidor: RAWG_API_KEY"}), 500

    params = {
        "key": rawg_key,
        "genres": genre,
        "page": page,
        "page_size": 20,
    }

    try:
        req = requests.get(RAWG_SEARCH_URL, params=params, timeout=10)
        if req.status_code == 200:
            data = req.json()
            resultados = []
            for jogo in data.get("results", []):
                generos_rawg = [g["name"] for g in jogo.get("genres", []) if g.get("name")]
                jogo_completo = map_rawg_game(jogo)
                jogo_completo["description"] = "Sem descrição."
                jogo_completo["genre"] = ", ".join(generos_rawg) if generos_rawg else "Vários"
                jogo_completo["studio"] = "Vários Estúdios"
                jogo_completo["modes"] = "Não informado"
                resultados.append(jogo_completo)

            try:
                _enrich_genre_games(resultados)
            except Exception as e_ia:
                app.logger.error("Erro no enriquecimento via IA: %s", e_ia)
                app.logger.exception("Falha ao enriquecer jogos de categoria com Gemini")

            return jsonify({"results": resultados, "next": bool(data.get("next"))})

        app.logger.error("Erro RAWG (Categorias): %s", req.status_code)
        return jsonify({"error": "Erro na busca de categorias"}), 502
    except Exception as e:
        app.logger.error("Erro interno (Categorias): %s", e)
        app.logger.exception("Falha ao buscar jogos por gênero na RAWG")
        return jsonify({"error": "Erro interno do servidor"}), 500


def _enrich_genre_games(resultados_base):
    """Completa estúdio, modos e sinopse com uma única chamada ao Gemini."""
    nomes_para_ia = [jogo.get("name") for jogo in resultados_base if jogo.get("name")]
    if not nomes_para_ia:
        return

    app.logger.info("Enriquecendo %s jogos com a IA...", len(nomes_para_ia))
    model = genai.GenerativeModel(GEMINI_MODEL)
    lista_nomes = "\n".join(f"- {nome}" for nome in nomes_para_ia)
    prompt_enrich = f"""
    Você é um especialista em videogames.
    Forneça detalhes curtos para CADA um dos seguintes jogos, na mesma ordem:
    {lista_nomes}

    Retorne APENAS um array JSON, com um objeto por jogo e EXATAMENTE estas chaves:
    "name": "o nome exato do jogo como enviei",
    "studio": "nome do estúdio desenvolvedor",
    "modes": "modos de jogo (ex: Single-player, Multiplayer)",
    "description": "Sinopse em português do Brasil com no máximo 2 linhas."
    Não adicione markdown, crases ou explicações. Apenas o array JSON.
    """

    response = model.generate_content(
        prompt_enrich,
        generation_config={"response_mime_type": "application/json"},
        request_options={"timeout": 35},
    )

    ia_data = parse_games_info(response.text, limit=None)
    app.logger.info("IA devolveu detalhes de %s jogos.", len(ia_data))
    ia_dict = {item["name"]: item for item in ia_data if item.get("name")}
    ia_dict_lower = {name.lower(): item for name, item in ia_dict.items()}

    for index, jogo in enumerate(resultados_base):
        nome_jogo = jogo.get("name") or ""
        extra = ia_dict.get(nome_jogo) or ia_dict_lower.get(nome_jogo.lower())
        if extra is None and index < len(ia_data):
            extra = ia_data[index]
        if not extra:
            continue
        if extra.get("studio"):
            jogo["studio"] = extra["studio"]
        if extra.get("modes"):
            jogo["modes"] = extra["modes"]
        if extra.get("description"):
            jogo["description"] = extra["description"]


if __name__ == "__main__":
    app.run(debug=True)
