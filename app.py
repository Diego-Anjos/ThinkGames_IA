import os

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import truststore
from whitenoise import WhiteNoise

load_dotenv()

# Usa os certificados confiáveis do sistema operacional; sem isso, redes com
# inspeção TLS quebram o handshake com a API do RAWG.
truststore.inject_into_ssl()

RAWG_API_KEY = os.getenv("RAWG_API_KEY")
RAWG_SEARCH_URL = "https://api.rawg.io/api/games"

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')


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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/suggest', methods=['POST'])
def suggest_games():
    """Busca jogos na API do RAWG a partir da descrição do usuário."""
    payload = request.get_json(silent=True) or {}
    user_description = (payload.get("description") or "").strip()
    if not user_description:
        return jsonify({"error": "A descrição do jogo é obrigatória."}), 400

    try:
        response = requests.get(
            RAWG_SEARCH_URL,
            params={
                "search": user_description,
                "key": RAWG_API_KEY,
                "page_size": 6,
            },
            timeout=10,
        )

        if response.status_code != 200:
            app.logger.error(
                "RAWG respondeu %s: %s", response.status_code, response.text[:300]
            )
            return jsonify({
                "error": f"A API do RAWG respondeu com o status {response.status_code}."
            }), 502

        data = response.json().get('results', [])
        return jsonify([map_rawg_game(game) for game in data])

    except Exception:
        app.logger.exception("Falha ao consultar a API do RAWG")
        return jsonify({
            "error": "Não foi possível consultar a API do RAWG. Tente novamente."
        }), 502


if __name__ == '__main__':
    app.run(debug=True)
