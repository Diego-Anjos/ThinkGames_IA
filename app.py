from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

# Banco de dados de jogos expandido e com estrutura aprimorada (gêneros e temas)
GAMES_DATABASE = [
    {
        "title": "The Witcher 3: Wild Hunt",
        "genres": ["rpg", "ação", "aventura"],
        "themes": ["fantasia", "medieval", "mundo aberto", "monstros", "narrativa"],
        "description": "Um RPG de ação com uma narrativa rica em um vasto mundo aberto de fantasia sombria, onde você caça monstros por dinheiro.",
        "platforms": ["Steam", "PlayStation", "Xbox", "Nintendo Switch"]
    },
    {
        "title": "Cyberpunk 2077",
        "genres": ["rpg", "ação", "fps"],
        "themes": ["cyberpunk", "futurista", "mundo aberto", "narrativa"],
        "description": "Explore a megalópole de Night City em um RPG de ação e aventura em mundo aberto onde você é um mercenário cyberpunk.",
        "platforms": ["Steam", "PlayStation", "Xbox"]
    },
    {
        "title": "Resident Evil Village",
        "genres": ["terror", "ação", "aventura"],
        "themes": ["sobrevivência", "horror", "vila", "primeira pessoa"],
        "description": "Um jogo de terror de sobrevivência que se passa em uma vila misteriosa e assustadora na Europa Oriental.",
        "platforms": ["Steam", "PlayStation", "Xbox"]
    },
    {
        "title": "DOOM Eternal",
        "genres": ["fps", "ação"],
        "themes": ["shooter", "demônios", "heavy metal", "rápido"],
        "description": "Unleash ultimate destruction as the Doom Slayer in an adrenaline-pumping, fast-paced first-person shooter with an epic heavy metal soundtrack.",
        "platforms": ["Steam", "PlayStation", "Xbox", "Nintendo Switch"]
    },
    {
        "title": "Apex Legends",
        "genres": ["fps", "ação"],
        "themes": ["shooter", "battle royale", "hero shooter", "multiplayer", "competitivo"],
        "description": "A free-to-play battle royale hero shooter where legendary characters with unique abilities team up to compete for fame and fortune on the frontier.",
        "platforms": ["Steam", "PlayStation", "Xbox", "Nintendo Switch"]
    },
    {
        "title": "Valorant",
        "genres": ["fps", "ação"],
        "themes": ["shooter", "tático", "hero shooter", "multiplayer", "competitivo"],
        "description": "A tactical 5v5 character-based FPS where precise gunplay meets unique agent abilities in a high-stakes, competitive environment.",
        "platforms": ["PC"]
    },
    {
        "title": "Stardew Valley",
        "genres": ["simulação", "rpg"],
        "themes": ["fazenda", "vila", "pixel art", "relaxante", "vida"],
        "description": "Você herdou a antiga fazenda do seu avô. Conseguirá aprender a viver da terra e transformar estes campos em um lar próspero?",
        "platforms": ["Steam", "PlayStation", "Xbox", "Nintendo Switch", "Mobile"]
    },
    {
        "title": "Red Dead Redemption 2",
        "genres": ["ação", "aventura"],
        "themes": ["mundo aberto", "velho oeste", "narrativa", "épico"],
        "description": "Uma história épica sobre honra e leialdade no alvorecer da era moderna na América, com um vasto e atmosférico mundo aberto.",
        "platforms": ["Steam", "PlayStation", "Xbox"]
    },
    # --- NOVOS JOGOS ADICIONADOS ---
    {
        "title": "Genshin Impact",
        "genres": ["rpg", "ação", "aventura"],
        "themes": ["anime", "fantasia", "mundo aberto", "gacha", "exploração"],
        "description": "Explore um vasto mundo de fantasia chamado Teyvat neste RPG de ação em mundo aberto com um estilo visual de anime e um sistema de combate elemental.",
        "platforms": ["PC", "PlayStation", "Mobile"]
    },
    {
        "title": "Persona 5 Royal",
        "genres": ["rpg", "j-rpg"],
        "themes": ["anime", "vida escolar", "turnos", "social", "moderno", "estiloso"],
        "description": "Viva a vida dupla de um estudante em Tóquio durante o dia e um ladrão fantasma à noite, invadindo as mentes dos corruptos neste aclamado J-RPG.",
        "platforms": ["PlayStation", "Xbox", "Steam", "Nintendo Switch"]
    },
    {
        "title": "Elden Ring",
        "genres": ["rpg", "ação", "aventura"],
        "themes": ["souls-like", "fantasia sombria", "mundo aberto", "difícil", "épico"],
        "description": "Levante-se, Maculado, e seja guiado pela graça para brandir o poder do Anel Prístino e se tornar um Lorde Prístino nas Terras Intermédias.",
        "platforms": ["Steam", "PlayStation", "Xbox"]
    },
    {
        "title": "Hollow Knight",
        "genres": ["metroidvania", "ação", "aventura", "plataforma"],
        "themes": ["indie", "insetos", "desafiador", "2d", "atmosférico"],
        "description": "Explore um vasto reino em ruínas de insetos e heróis. Um desafiador jogo de ação e aventura 2D no estilo Metroidvania com um belo estilo de arte.",
        "platforms": ["Steam", "PlayStation", "Xbox", "Nintendo Switch"]
    },
    {
        "title": "The Legend of Zelda: Breath of the Wild",
        "genres": ["aventura", "ação", "rpg"],
        "themes": ["mundo aberto", "exploração", "fantasia", "sobrevivência", "puzzle"],
        "description": "Explore um mundo de descobertas, exploração e aventura em The Legend of Zelda: Breath of the Wild, um jogo que quebra barreiras na aclamada série.",
        "platforms": ["Nintendo Switch"]
    },
    {
        "title": "Ghost of Tsushima",
        "genres": ["ação", "aventura"],
        "themes": ["mundo aberto", "samurai", "japão feudal", "furtivo", "narrativa"],
        "description": "Forje um novo caminho e trave uma guerra não convencional pela liberdade de Tsushima neste épico de ação e aventura em um deslumbrante Japão feudal.",
        "platforms": ["PlayStation"]
    }
]

def analyze_user_input(text):
    """Extrai palavras-chave do texto do usuário."""
    text = re.sub(r'[^\w\s]', '', text.lower())
    return set(text.split())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/suggest', methods=['POST'])
def suggest_games():
    """Endpoint da API que recebe a descrição e retorna sugestões com lógica de pontuação."""
    user_description = request.json.get('description', '')
    if not user_description:
        return jsonify({"error": "Descrição não pode estar vazia."}), 400

    user_keywords = analyze_user_input(user_description)
    
    recommendations = []
    for game in GAMES_DATABASE:
        score = 0
        # Gêneros têm um peso maior (mais importantes)
        genre_matches = user_keywords.intersection(game["genres"])
        score += len(genre_matches) * 3  # 3 pontos por gênero correspondente

        # Temas têm um peso menor
        theme_matches = user_keywords.intersection(game["themes"])
        score += len(theme_matches) * 1  # 1 ponto por tema correspondente

        if score > 0:
            recommendations.append({"game": game, "score": score})

    # Ordena as recomendações pela pontuação
    sorted_recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)
    
    final_suggestions = [rec['game'] for rec in sorted_recommendations]

    return jsonify(final_suggestions)

if __name__ == '__main__':
    app.run(debug=True)