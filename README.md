<div align="center">

# 🎮 Think Games AI

**Apresentado como Trabalho na Faculdade FECAF**

<br>

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

<br>

> Buscador inteligente que traduz suas ideias em recomendações reais de jogos, integrando IA avançada com dados completos de catálogo, avaliações e plataformas.

</div>

---

## ✨ Visão Geral

Muitos jogadores sentem dificuldade em encontrar jogos que realmente correspondam aos seus gostos específicos, para além dos títulos mais populares. O **Think Games AI** resolve este problema permitindo que os usuários descrevam o cenário perfeito de um jogo em linguagem natural. Utilizando a API do Google Gemini aliada ao imenso banco de dados da RAWG, o sistema compreende contextos, emoções e comparações para sugerir títulos precisos e justificados.

## 🚀 Funcionalidades

- **Busca por Linguagem Natural:** Descreva o jogo que você quer com total liberdade (ex: *"Quero um jogo parecido com Resident Evil, mas no espaço"*).
- **Curadoria com Inteligência Artificial:** A IA atua como um especialista, entendendo o contexto do seu pedido e justificando o porquê de cada recomendação.
- **Enriquecimento em Tempo Real:** Nas buscas por categorias, o sistema utiliza IA assíncrona para gerar descrições e detalhes de jogos em português, preenchendo lacunas de APIs públicas.
- **Interface Moderna e Responsiva:** Design elegante no estilo *Dark/Tech*, totalmente responsivo (Mobile-First) e amigável.
- **Catálogo Abrangente:** Alimentado pela API da RAWG, cobrindo milhares de jogos, gêneros e plataformas.

---

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python 3, Flask
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla), SVG Inline
- **APIs:**
  - [Google Gemini API](https://aistudio.google.com/) (Motor de LLM / Curadoria)
  - [RAWG Video Games Database API](https://rawg.io/apidocs) (Catálogo e Imagens)
- **Deploy:** Preparado para Vercel (Serverless)

---

## ⚙️ Como rodar o projeto localmente

### Pré-requisitos

Você precisará ter o [Python](https://www.python.org/) instalado na sua máquina e chaves de API válidas do Google Gemini e da RAWG.

### Passos

1. **Clone o repositório:**

```bash
git clone https://github.com/Diego-Anjos/ThinkGames_IA.git
cd ThinkGames_IA
```

2. **Crie e ative um ambiente virtual:**

```bash
python -m venv venv
```

```bash
# No Windows:
venv\Scripts\activate
```

```bash
# No Linux/Mac:
source venv/bin/activate
```

3. **Instale as dependências:**

```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente:**

Crie um arquivo chamado `.env` na raiz do projeto e adicione suas chaves:

```env
RAWG_API_KEY=sua_chave_da_rawg_aqui
GEMINI_API_KEY=sua_chave_do_gemini_aqui
```

5. **Inicie o servidor:**

```bash
python app.py
```

O projeto estará rodando em [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

---

## 👨‍💻 Autor

**Diego Anjos**

Estudante de Gestão da Tecnologia da Informação — FECAF
