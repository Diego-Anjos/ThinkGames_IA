# Think Games AI 🎮

> Um sistema inteligente de recomendação de jogos baseado em Inteligência Artificial. Imagine o seu jogo perfeito, descreva-o com suas palavras e deixe nossa IA descobrir títulos personalizados para você.

Este projeto foi desenvolvido como parte da atividade para o curso de Graduação em Gestão da Tecnologia da Informação da Faculdade FECAF.

## 📜 Visão Geral

Muitos jogadores sentem dificuldade em encontrar jogos que realmente correspondam aos seus gostos específicos, para além dos títulos mais populares. O Think Games AI resolve este problema permitindo que os usuários descrevam um jogo em linguagem natural, e utiliza uma IA com lógica de pontuação para analisar o texto e sugerir os títulos mais relevantes em seu banco de dados.

## ✨ Features

-   **Busca por Linguagem Natural:** Descreva o jogo que você quer com total liberdade.
-   **IA com Lógica de Pontuação:** O sistema analisa gêneros e temas com pesos diferentes para fornecer recomendações mais precisas.
-   **Interface Moderna e Intuitiva:** Um design limpo e direto ao ponto, focado na experiência do usuário.
-   **Banco de Dados Curado:** Uma lista de jogos variada para cobrir diversos gêneros e estilos.

## 💻 Tecnologias Utilizadas

-   **Backend:** Python 3, Flask
-   **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
-   **Banco de Dados:** Simulado em memória (Lista de Dicionários Python)

---

## 🚀 Como Executar o Projeto Localmente

Siga as instruções abaixo para configurar e executar a aplicação em sua máquina local.

### **Pré-requisitos**

-   [Python 3.8+](https://www.python.org/downloads/)
-   [Git](https://git-scm.com/downloads)

### **Passo a Passo**

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/seu-usuario/think-games-ai.git](https://github.com/seu-usuario/think-games-ai.git)
    ```

2.  **Acesse a pasta do projeto:**
    ```bash
    cd think-games-ai
    ```

3.  **Crie e ative um ambiente virtual:**
    * No Windows:
        ```bash
        python -m venv .venv
        .\.venv\Scripts\activate
        ```
    * No macOS ou Linux:
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

4.  **Instale as dependências:**
    O projeto possui um arquivo `requirements.txt` para facilitar a instalação das bibliotecas necessárias.
    ```bash
    pip install -r requirements.txt
    ```
    *(Se você ainda não criou o arquivo `requirements.txt`, crie-o na raiz do projeto com o seguinte conteúdo antes de rodar o comando acima):*
    ```
    Flask
    ```

5.  **Execute a aplicação:**
    ```bash
    python app.py
    ```

6.  **Acesse no navegador:**
    Abra seu navegador e acesse o seguinte endereço:
    [http://xxx.x.x.x

Pronto! A aplicação Think Games AI estará rodando localmente.

## 📂 Estrutura de Arquivos

```
.
├── app.py              # Lógica do backend e da IA
├── requirements.txt      # Dependências do Python
├── static/
│   └── style.css       # Estilos da aplicação
└── templates/
    └── index.html      # Estrutura da página web
```

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
