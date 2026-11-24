# 🖱️ Mouse Virtual — Controle por Movimentos e Voz (TCC)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Visão%20Computacional-5C3EE8?logo=opencv&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-0097A7)
![Windows](https://img.shields.io/badge/Windows-Executável%20Único-0078D6?logo=windows&logoColor=white)

Software de **acessibilidade e controle computacional sem mouse ou teclado físico**, desenvolvido como Trabalho de Conclusão de Curso (TCC).  
Utilizando apenas uma webcam (ou celular conectado via **DroidCam USB**), o usuário controla o cursor com movimentos da cabeça, realiza cliques piscando os olhos, ajusta a sensibilidade com gestos manuais e dita textos por voz em Português (`pt-BR`).

---

## ✨ Principais Recursos

- **🎯 Joystick Facial com Âncora Dinâmica:** a zona neutra (*deadzone*) acompanha automaticamente a posição do rosto enquanto a embreagem está solta, permitindo uso confortável em qualquer postura ou inclinação.
- **🪶 Filtro Anti-Tremor (EMA):** suavização em tempo real que elimina micro-oscilações da câmera para movimentos precisos.
- **🤏 Embreagem de Precisão:** o cursor só se move enquanto polegar e indicador estiverem praticamente encostados; ao afastar os dedos, o movimento pausa na hora.
- **👁️ Cliques Independentes por Piscada (EAR):** clique esquerdo e direito funcionam a qualquer momento, mesmo com o movimento pausado, ignorando piscadas naturais simultâneas.
- **🎙️ Ditado e Edição por Voz (`PT-BR`):** transcrição em segundo plano sem congelar o vídeo, preservando acentuação e `ç`, com comandos dedicados de edição.
- **🔔 Segundo Plano, Bandeja e Avisos Flutuantes:** roda sem janela de terminal, possui ícone na bandeja do sistema (*System Tray*) e exibe notificações flutuantes discretas que não roubam o foco de onde você estiver digitando.

---

## 🖐️ Guia Rápido de Gestos e Comandos

### Movimentos e Gestos

| Ação | Gesto / Comando |
| :--- | :--- |
| **Mover o cursor** | Mantenha **Polegar + Indicador** juntos (pinça) e mova a cabeça |
| **Pausar movimento** | Afaste o polegar do indicador |
| **Clique Esquerdo** | Pisque apenas o **olho esquerdo** |
| **Clique Direito** | Pisque apenas o **olho direito** |
| **Aumentar sensibilidade (`+5`)** | Junte **Polegar + Dedo Médio** (ou tecla `+`) |
| **Diminuir sensibilidade (`-5`)** | Junte **Polegar + Dedo Anelar** (ou tecla `-`) |
| **Ativar ditado por voz** | Junte **Polegar + Dedo Mindinho** |
| **Rodar em segundo plano** | Feche a janela da câmera (`X`) ou pressione `h` |
| **Encerrar aplicativo** | Pressione `q` na câmera ou clique em **Sair** no ícone da bandeja |

### Comandos de Voz (durante o ditado)

| Você fala | O que o software faz |
| :--- | :--- |
| Qualquer frase normal | Digita/cola o texto automaticamente onde o cursor estiver |
| **`"apagar"`** (isolado) | Apaga a última palavra inteira (`Ctrl + Backspace`) |
| **`"espaço"`** (isolado) | Insere um espaço entre palavras |

> 💡 **Dica:** Os comandos `"apagar"` e `"espaço"` só são executados quando ditos isoladamente, evitando que frases normais contendo essas palavras disparem ações por engano.

---

## 🚀 Como Usar (Sem Instalar Nada — Recomendado)

1. Acesse a página de [**Releases**](https://github.com/fernando01303/TCC/releases) deste repositório e baixe o arquivo **`MouseVirtual.exe`**.
2. Conecte sua webcam ou abra o **DroidCam via cabo USB** (veja o porquê no relatório de erros).
3. Dê dois cliques em `MouseVirtual.exe` — uma tela animada de carregamento aparecerá enquanto a câmera é iniciada.
4. Para usar sem a janela da câmera na tela, basta fechá-la (`X` ou `h`): o controle continuará ativo em segundo plano e o ícone ficará visível perto do relógio do Windows.

---

## 🛠️ Como Executar pelo Código-Fonte (Desenvolvedores)

```bash
# 1. Clonar o repositório
git clone https://github.com/fernando01303/TCC.git
cd TCC

# 2. Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependências (MediaPipe < 1.0 é obrigatório)
pip install -r requirements.txt

# 4. Executar o sistema
python mouse_virtual.py
```

### Gerar o executável único (`.exe`)

```bash
pyinstaller --onefile --noconsole --splash splash.png --collect-all mediapipe --name MouseVirtual mouse_virtual.py
```

---

## 📚 Documentação Adicional

- [**RELATORIO_DE_ERROS.md**](./RELATORIO_DE_ERROS.md) — Registro detalhado dos problemas encontrados durante o desenvolvimento (incluindo incompatibilidades do MediaPipe e soluções com DroidCam USB) e suas respectivas soluções.
