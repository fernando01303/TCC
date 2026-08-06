# 🐛 REGISTRO DE BUGS E SOLUÇÕES — Mouse Virtual (TCC)

Este arquivo documenta todos os erros encontrados durante o desenvolvimento e suas respectivas soluções. CONSULTAR SEMPRE antes de tentar corrigir um bug.

*Última atualização: 2026-08-06*

---

## BUG #1 — Python não encontrado no PATH do Windows

**SINTOMA:**
"Python was not found; run without arguments to install from the Microsoft Store"
Os comandos `python`, `pip`, `py` não são reconhecidos pelo terminal.

**CAUSA:**
O Python não estava instalado no sistema, ou o terminal (PowerShell) foi aberto ANTES da instalação do Python e ainda carregava o PATH antigo.

**SOLUÇÃO:**
1. Instalar Python via: `winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements`
2. Após instalar, **FECHAR E REABRIR** o terminal para que o novo PATH seja carregado.
3. Se rodar via script automatizado, forçar reload do PATH no PowerShell.

---

## BUG #2 — mediapipe não possui atributo 'solutions'

**SINTOMA:**
`AttributeError: module 'mediapipe' has no attribute 'solutions'`

**CAUSA:**
O MediaPipe versão 1.0.0 (lançado em 2025+) removeu a API legada `mp.solutions.*` e migrou para uma nova API baseada em `mp.tasks`. Nosso código usa a API legada.

**SOLUÇÃO:**
Instalar uma versão do MediaPipe anterior à 1.0:
`pip install mediapipe==0.10.14`

NÃO usar: `pip install mediapipe` (instala a 1.0+ que quebra o código).
O comando correto completo é:
`pip install opencv-python "mediapipe<1.0" pyautogui`

---

## BUG #3 — Tela verde ao usar DroidCam como câmera

**SINTOMA:**
A janela do OpenCV abre, mas exibe uma tela inteiramente VERDE. O rosto não aparece, o MediaPipe não detecta nada, o mouse não se move.

**CAUSA:**
O DroidCam transmite vídeo em formato AVC/H.264. Quando o OpenCV abre a câmera sem especificar o codec, ele tenta decodificar os frames como YUV/NV12 bruto, resultando em uma imagem toda verde (os bytes são interpretados incorretamente).

**SOLUÇÃO:**
Tentar múltiplas estratégias de codec na inicialização da câmera (H264, MJPG, DSHOW). 
IMPORTANTE: Descartar os primeiros 5-10 frames após abrir a câmera, pois muitas câmeras virtuais enviam frames corrompidos nos primeiros quadros.

---

## BUG #4 — cv2.VideoCapture trava/congela ao abrir câmera inexistente

**SINTOMA:**
O script fica travado na linha `cv2.VideoCapture(i)` sem avançar. Nenhuma mensagem de erro aparece. O programa não responde.

**CAUSA:**
No Windows, o OpenCV pode travar por tempo indeterminado ao tentar abrir um índice de câmera que não existe, especialmente sem o backend DSHOW.

**SOLUÇÃO:**
Rodar cada tentativa de `cv2.VideoCapture()` em uma THREAD SEPARADA com timeout (ver BUG #6).

---

## BUG #5 — print() do Python não aparece nos logs em tempo real

**SINTOMA:**
O script parece estar travado (sem nenhum output), mas na verdade está rodando. Os `print()` só aparecem quando o programa encerra ou o buffer enche.

**CAUSA:**
O Python faz buffer do stdout por padrão quando não está rodando em terminal interativo.

**SOLUÇÃO:**
Adicionar no início do script:
```python
import functools
print = functools.partial(print, flush=True)
```

---

## BUG #6 — cv2.VideoCapture() trava INDEFINIDAMENTE (não retorna)

**SINTOMA:**
O script parece travar logo na inicialização. Nenhum print() aparece. O processo fica vivo mas não faz nada.

**CAUSA:**
Em alguns sistemas Windows, `cv2.VideoCapture(indice)` pode travar INDEFINIDAMENTE ao tentar abrir uma câmera que não existe ou que está em estado inconsistente.

**SOLUÇÃO:**
Rodar cada tentativa de `cv2.VideoCapture()` em uma THREAD SEPARADA com timeout. Se a thread não retornar em 5 segundos, ela é considerada travada e abandonada.

---

## BUG #7 — Tela verde PERSISTE mesmo trocando codec (H264/MJPG/auto)

**SINTOMA:**
Ao abrir a câmera virtual do DroidCam (índice 0) com `cv2.VideoCapture()`, TODOS os codecs resultam em tela verde.

**CAUSA:**
O driver virtual do DroidCam no Windows registra a câmera como dispositivo MSMF, mas entrega os frames em formato H.264 comprimido. O OpenCV (via MSMF ou DSHOW) não possui decodificador H.264 integrado para câmeras virtuais.

**SOLUÇÃO DEFINITIVA:**
Conectar DIRETAMENTE no stream HTTP do DroidCam no celular, usando a URL:
`http://<IP_DO_CELULAR>:4747/video`
O backend FFmpeg do OpenCV consegue decodificar o H.264 HTTP nativamente.

---

## BUG #8 — Falha na conexão Wi-Fi / Instabilidade da Tela Verde

**SINTOMA:**
A conexão Wi-Fi do DroidCam via HTTP pode falhar, travar ou continuar retornando tela verde dependendo do firewall.

**CAUSA:**
A rede local pode bloquear portas, ou o stream Wi-Fi pode sofrer quedas que corrompem a decodificação do frame.

**SOLUÇÃO DEFINITIVA:**
Conectar o DroidCam via **cabo USB**. Isso garante estabilidade máxima na conexão. Ao usar o cabo USB, a câmera passa a funcionar como um dispositivo local normal (índice 0, 1 ou 2) sendo reconhecida instantaneamente sem usar lógicas de rede, garantindo que o OpenCV receba vídeo descomprimido limpo.
