import json
import logging
import os
import re

import requests

# Injeta os certificados do sistema operacional antes de carregar a IA.
# Sem isso, redes com inspeção TLS (ex.: acadêmica) quebram o handshake.
import truststore
truststore.inject_into_ssl()

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from whitenoise import WhiteNoise

# Carrega o .env ANTES de ler as chaves
load_dotenv()

gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not gemini_key:
    raise ValueError("A chave GEMINI_API_KEY não está configurada no arquivo .env.")

# O SDK novo fala HTTP puro (httpx), então respeita o truststore e o timeout.
gemini_client = genai.Client(api_key=gemini_key)

RAWG_API_KEY = (os.getenv("RAWG_API_KEY") or "").strip()
RAWG_SEARCH_URL = "https://api.rawg.io/api/games"
RAWG_PLACEHOLDER_IMAGE = "/static/images/placeholder.jpg"
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "gemini-3.6-flash").strip()
MODELOS_FALLBACK = [
    GEMINI_MODEL,
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

# thinking_level "low" mantém a qualidade da curadoria sem o custo de latência
# do raciocínio estendido, que é o padrão do modelo e levava ~60s por busca.
GEMINI_TIMEOUT_MS = 60_000
THINKING = types.ThinkingConfig(thinking_level="low")

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root="static/")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
app.logger.setLevel(logging.INFO)

# O SDK loga cada requisição HTTP e avisa sobre function calling automático,
# que não é usado aqui. Silenciar mantém o log da busca legível.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)


def map_rawg_game(game):
    """Normaliza um jogo do RAWG nos campos esperados pelo frontend."""
    platforms = []
    for item in game.get("platforms") or []:
        platform_name = (item.get("platform") or {}).get("name")
        if platform_name:
            platforms.append(platform_name)

    return {
        "name": game.get("name") or "Jogo sem nome",
        "background_image": game.get("background_image") or RAWG_PLACEHOLDER_IMAGE,
        "rating": game.get("rating") or 0,
        "released": game.get("released") or "",
        "platforms": platforms,
    }


def _card_from_ia(game, rawg_game=None):
    """Monta o card com dados da IA e, se houver, capa/plataformas da RAWG."""
    if rawg_game:
        card = map_rawg_game(rawg_game)
    else:
        card = {
            "name": game.get("name") or "Jogo sem nome",
            "background_image": RAWG_PLACEHOLDER_IMAGE,
            "rating": 0,
            "released": "",
            "platforms": [],
        }
    card["description"] = game.get("description", "Sem descrição.")
    card["genre"] = game.get("genre", "Vários")
    card["studio"] = game.get("studio", "Desconhecido")
    card["modes"] = game.get("modes", "Não informado")
    return card


def extract_json_block(raw_text):
    """Isola o JSON da resposta da IA, descartando markdown e texto solto em volta.

    Devolve None quando não há um bloco JSON reconhecível no texto.
    """
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"(\{.*\}|\[.*\])", text.strip(), re.DOTALL)
    return match.group(1).strip() if match else None


def parse_games_info(raw_text, limit=6):
    """Extrai jogos com nome, estúdio, gênero e descrição a partir do JSON da IA."""
    payload = extract_json_block(raw_text)
    if payload is None:
        raise ValueError("A IA não devolveu um bloco JSON reconhecível.")
    return extract_games_info(json.loads(payload), limit=limit)


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


def _generate_with_fallback(contents):
    """Chama o Gemini tentando modelos em ordem até um responder sem erro 429."""
    ultimo_erro_cota = None
    for indice, modelo in enumerate(MODELOS_FALLBACK):
        try:
            return gemini_client.models.generate_content(
                model=modelo,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=THINKING,
                    http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
                ),
            )
        except genai_errors.APIError as e:
            if e.code != 429:
                raise
            ultimo_erro_cota = e
            proximo = (
                MODELOS_FALLBACK[indice + 1]
                if indice + 1 < len(MODELOS_FALLBACK)
                else None
            )
            if proximo:
                app.logger.warning(
                    "Cota do modelo %s excedida, tentando modelo %s...",
                    modelo,
                    proximo,
                )
            else:
                app.logger.warning(
                    "Cota do modelo %s excedida. Sem mais modelos de fallback.",
                    modelo,
                )
    raise ultimo_erro_cota


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
            "2. Conectando com a IA Gemini (%s, thinking low, timeout de %ss)...",
            " -> ".join(MODELOS_FALLBACK),
            GEMINI_TIMEOUT_MS // 1000,
        )
        prompt = f"""
        Você é um curador especialista em videogames e um motor de recomendação avançado.
        Analise o pedido do usuário: "{description}"

        REGRA CRÍTICA DE FORMATAÇÃO: Você está retornando um JSON. NUNCA use aspas duplas (") dentro do conteúdo das strings (ex: descrições ou nomes). Se precisar destacar algo ou fazer citações, use aspas simples (').

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

        response = _generate_with_fallback(prompt)

        app.logger.info("3. Resposta bruta do Gemini recebida!")

        raw_text = extract_json_block(response.text)
        if raw_text is None:
            app.logger.error(
                "Nenhum bloco JSON encontrado na resposta da IA. Resposta bruta: %s",
                response.text,
            )
            return jsonify({
                "error": "A IA retornou um formato inválido. Tente novamente."
            }), 500

        try:
            ia_data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            app.logger.error(
                "Erro ao decodificar JSON da IA: %s. Texto extraído: %s", e, raw_text
            )
            return jsonify({
                "error": "Erro no processamento da IA. Tente novamente."
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
            try:
                req = requests.get(
                    RAWG_SEARCH_URL,
                    params={
                        "key": rawg_key,
                        "search": name,
                        "page_size": 1,
                    },
                    timeout=10,
                )
            except requests.exceptions.Timeout:
                app.logger.warning(
                    "    [AVISO] Timeout da RAWG ao buscar '%s'. Usando dados parciais.",
                    name,
                )
                resultados_finais.append(_card_from_ia(game))
                continue
            except requests.exceptions.RequestException as e:
                app.logger.warning(
                    "    [AVISO] Falha de conexão com a RAWG ao buscar '%s': %s",
                    name,
                    e,
                )
                resultados_finais.append(_card_from_ia(game))
                continue

            if req.status_code == 200:
                rawg_data = req.json()
                if rawg_data.get("results"):
                    jogo_encontrado = rawg_data["results"][0]
                    resultados_finais.append(_card_from_ia(game, jogo_encontrado))
                    app.logger.info("    [OK] Encontrado!")
                else:
                    app.logger.warning(
                        "    [AVISO] Jogo não retornado na busca RAWG. Usando dados parciais."
                    )
                    resultados_finais.append(_card_from_ia(game))
            else:
                app.logger.warning(
                    "    [AVISO] RAWG retornou status %s ao buscar '%s'. Usando dados parciais.",
                    req.status_code,
                    name,
                )
                resultados_finais.append(_card_from_ia(game))

        app.logger.info("6. Busca finalizada com sucesso! Retornando ao frontend.")
        response_obj = {"ai_message": ai_message, "results": resultados_finais}
        try:
            # dumps escapa aspas, barras e acentos, evitando JSON inválido no navegador.
            return Response(json.dumps(response_obj), mimetype="application/json")
        except TypeError as e:
            app.logger.error("Erro na serialização manual: %s", e)
            return jsonify({"error": "Erro na formatação dos dados finais."}), 500

    except genai_errors.APIError as e:
        if e.code == 429:
            app.logger.error("[QUOTA] Limite de uso da IA atingido: %s", e)
            return jsonify({
                "error": "O limite de uso da IA foi atingido. Aguarde um instante e tente novamente."
            }), 429

        app.logger.error("[API] A IA retornou erro %s: %s", e.code, e)
        return jsonify({
            "error": "A IA está sobrecarregada agora. Tente novamente em alguns segundos."
        }), 503

    except Exception as e:
        mensagem = str(e)
        if "timed out" in mensagem.lower() or "timeout" in mensagem.lower():
            app.logger.error("[TIMEOUT] A IA não respondeu no tempo limite: %s", mensagem)
            return jsonify({
                "error": "A IA demorou demais para responder. Tente novamente em alguns segundos."
            }), 504

        app.logger.error("[ERRO GRAVE] O processamento falhou: %s", mensagem)
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
    NUNCA use aspas duplas (") dentro do conteúdo das strings; use aspas simples (').
    Não adicione markdown, crases ou explicações. Apenas o array JSON.
    """

    response = _generate_with_fallback(prompt_enrich)

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
