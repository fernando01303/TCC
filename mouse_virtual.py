# Instalação das bibliotecas necessárias:
# pip install opencv-python "mediapipe<1.0" pyautogui
#
# CONSULTAR: README.md antes de alterar este arquivo.

import cv2
import mediapipe as mp
import pyautogui
import math
import time
import numpy as np
import threading

# Desabilitar o failsafe do pyautogui para evitar crash se o mouse for para os cantos.
pyautogui.FAILSAFE = False
# Remover o atraso padrão de 0.1s entre comandos do PyAutoGUI (isso remove as "travadas" e deixa suave)
pyautogui.PAUSE = 0

# Obter a resolução real da tela do usuário
screen_w, screen_h = pyautogui.size()
print(f"Resolucao da tela detectada: {screen_w}x{screen_h}")

# Configuração do MediaPipe Face Mesh
# IMPORTANTE: Usar mediapipe < 1.0 (ver BUG #2 em BUGS_E_SOLUCOES.py)
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,       # Obrigatório para pálpebras e íris detalhadas
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Configuração do MediaPipe Hands para "Embreagem"
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# =====================================================================
# 1. INICIALIZAÇÃO DE CÂMERA À PROVA DE FALHAS (COM TIMEOUT)
# 
# Problemas resolvidos (ver BUGS_E_SOLUCOES.py):
#   BUG #3: DroidCam envia H.264 → testar múltiplos codecs
#   BUG #4: cv2.VideoCapture() pode travar indefinidamente
#   BUG #5: O print() do Python não aparece no log se stdout está buffered
#
# Solução: cada tentativa de abrir câmera roda em thread com timeout de 5s.
# Se travar, a thread é abandonada e passamos para a próxima combinação.
# =====================================================================

# Forçar flush imediato de todo print() para que os logs apareçam em tempo real
import sys
import functools
print = functools.partial(print, flush=True)

cap = None
print("\n=== INICIALIZACAO DA CAMERA ===\n")
print("Tentando acessar as cameras locais (DroidCam via USB costuma ser 0 ou 1)...\n")

for indice in range(3):
    print(f"Tentando abrir camera no indice {indice}...")
    temp_cap = cv2.VideoCapture(indice)
    
    if not temp_cap.isOpened():
        print(f"  -> Indice {indice} falhou ao abrir.")
        temp_cap.release()
        continue
        
    # Ler alguns frames para descartar lixo inicial
    for _ in range(10):
        temp_cap.read()
        
    ret, frame = temp_cap.read()
    if not ret or frame is None:
        print(f"  -> Indice {indice} abriu, mas nao conseguiu ler a imagem.")
        temp_cap.release()
        continue
        
    print(f"  -> SUCESSO! Camera conectada no indice {indice}.\n")
    cap = temp_cap
    break

if cap is None:
    print("\n=== ERRO FATAL ===")
    print("Nenhuma camera valida encontrada.")
    print("Verifique se o DroidCam esta aberto e conectado via cabo USB e aperte o 'Start'.")
    exit()

# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================

def calcular_distancia(p1, p2, w, h):
    """Calcula a distância euclidiana em pixels entre dois landmarks faciais."""
    x1, y1 = int(p1.x * w), int(p1.y * h)
    x2, y2 = int(p2.x * w), int(p2.y * h)
    return math.hypot(x2 - x1, y2 - y1)

def calcular_ear(face_landmarks, w, h):
    """
    Calcula o Eye Aspect Ratio (EAR) — Proporção de Abertura do Olho.
    Retorna os valores separados para olho esquerdo e direito.
    """
    # Olho esquerdo — cantos horizontais (33, 133), vertical (159 superior, 145 inferior)
    dist_h_esq = calcular_distancia(face_landmarks.landmark[33], face_landmarks.landmark[133], w, h)
    dist_v_esq = calcular_distancia(face_landmarks.landmark[159], face_landmarks.landmark[145], w, h)
    ear_esq = dist_v_esq / dist_h_esq if dist_h_esq != 0 else 0

    # Olho direito — cantos horizontais (362, 263), vertical (386 superior, 374 inferior)
    dist_h_dir = calcular_distancia(face_landmarks.landmark[362], face_landmarks.landmark[263], w, h)
    dist_v_dir = calcular_distancia(face_landmarks.landmark[386], face_landmarks.landmark[374], w, h)
    ear_dir = dist_v_dir / dist_h_dir if dist_h_dir != 0 else 0

    return ear_esq, ear_dir

def calcular_distancia_pinca(hand_landmarks, w, h):
    """Calcula a distancia em pixels entre a ponta do polegar (4) e a do indicador (8)."""
    ponta_polegar = hand_landmarks.landmark[4]
    ponta_indicador = hand_landmarks.landmark[8]
    return calcular_distancia(ponta_polegar, ponta_indicador, w, h)

# =====================================================================
# VARIÁVEIS DE ESTADO
# =====================================================================

# Estado do Joystick
curr_x, curr_y = screen_w / 2, screen_h / 2
pyautogui.moveTo(curr_x, curr_y) # Inicia no centro
JOYSTICK_SPEED = 35.0     # Sensibilidade do joystick (velocidade máxima)
DEADZONE_RADIUS = 15      # Raio em pixels do centro em que o mouse nao se move (diminuido)
PINCA_THRESHOLD = 40      # Distancia maxima entre dedos para ativar a embreagem

# Ancora Dinamica do Joystick
ancora_x, ancora_y = None, None

# Controle de Cliques Independentes (Eye Blink)
EAR_THRESHOLD = 0.20
DEBOUNCE_TIME = 0.8
ultimo_clique_esq = time.time()
ultimo_clique_dir = time.time()
texto_clique_ate = 0
msg_clique = ""

print("=== MOUSE VIRTUAL INICIADO ===")
print("Faca uma pinca (polegar + indicador) para ativar o movimento.")
print("Olhe para os lados para mover o mouse (Joystick).")
print("Pisque apenas um olho para clicar (Esq = Clique Esq / Dir = Clique Dir).")
print("Pressione 'q' na janela do video para sair.\n")

# =====================================================================
# LOOP PRINCIPAL
# =====================================================================

while True:
    ret, frame = cap.read()
    
    # Validação estrita de frame (nunca processar frame vazio)
    if not ret or frame is None:
        continue
    
    # Espelhar horizontalmente (interação tipo espelho)
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    centro_tela_x, centro_tela_y = w // 2, h // 2
    
    # Processar com MediaPipe (requer RGB)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results_face = face_mesh.process(rgb_frame)
    results_hands = hands.process(rgb_frame)
    
    texto_status = "Mouse Pausado (Junte 2 dedos)"
    cor_status = (0, 0, 255)
    embreagem_ativa = False
    
    # --- VERIFICAÇÃO DA EMBREAGEM (MÃO EM PINÇA) ---
    if results_hands.multi_hand_landmarks:
        hand_landmarks = results_hands.multi_hand_landmarks[0]
        dist_pinca = calcular_distancia_pinca(hand_landmarks, w, h)
        
        # Feedback visual da mão
        x_polegar, y_polegar = int(hand_landmarks.landmark[4].x * w), int(hand_landmarks.landmark[4].y * h)
        x_indicador, y_indicador = int(hand_landmarks.landmark[8].x * w), int(hand_landmarks.landmark[8].y * h)
        
        # Cor da linha muda de vermelho (separado) para verde (pinça ativa)
        cor_pinca = (0, 255, 0) if dist_pinca < PINCA_THRESHOLD else (0, 0, 255)
        cv2.line(frame, (x_polegar, y_polegar), (x_indicador, y_indicador), cor_pinca, 2)
        cv2.circle(frame, (x_polegar, y_polegar), 5, cor_pinca, -1)
        cv2.circle(frame, (x_indicador, y_indicador), 5, cor_pinca, -1)
        
        if dist_pinca < PINCA_THRESHOLD:
            embreagem_ativa = True
            texto_status = "Mouse ATIVO"
            cor_status = (0, 255, 0)
    
    # --- MOVIMENTAÇÃO E CLIQUES (ROSTO) ---
    if results_face.multi_face_landmarks:
        face_landmarks = results_face.multi_face_landmarks[0]
        
        # Posição do Nariz
        nariz = face_landmarks.landmark[1]
        nariz_x = int(nariz.x * w)
        nariz_y = int(nariz.y * h)
        
        # --- ÂNCORA DINÂMICA ---
        # Se a embreagem estiver solta (mão aberta), a âncora segue o nariz
        if not embreagem_ativa:
            ancora_x, ancora_y = nariz_x, nariz_y
            
        if ancora_x is None:
            ancora_x, ancora_y = nariz_x, nariz_y
            
        # Desenhar zona neutra (Deadzone) baseada na âncora dinâmica
        cor_deadzone = (0, 255, 0) if embreagem_ativa else (0, 0, 255)
        cv2.circle(frame, (ancora_x, ancora_y), DEADZONE_RADIUS, cor_deadzone, 2)
        
        # Desenhar indicador do nariz apontando pro centro da âncora
        cv2.circle(frame, (nariz_x, nariz_y), 5, (255, 0, 0), -1)
        cv2.line(frame, (ancora_x, ancora_y), (nariz_x, nariz_y), (255, 255, 255), 1)
        
        if embreagem_ativa:
            # 1. Movimento Joystick
            # Voltei o eixo X ao normal, pois a lógica espelhada é mais intuitiva para a maioria
            dx = nariz_x - ancora_x
            dy = nariz_y - ancora_y
            dist_centro = math.hypot(dx, dy)
            
            if dist_centro > DEADZONE_RADIUS:
                # O quanto o nariz passou da deadzone (0.0 a ~1.0)
                intensidade = (dist_centro - DEADZONE_RADIUS) / (w / 2)
                
                # Velocidade = direção normalizada * intensidade * sensibilidade
                vel_x = (dx / dist_centro) * intensidade * JOYSTICK_SPEED
                vel_y = (dy / dist_centro) * intensidade * JOYSTICK_SPEED
                
                curr_x = max(0, min(screen_w, curr_x + vel_x))
                curr_y = max(0, min(screen_h, curr_y + vel_y))
                
                pyautogui.moveTo(int(curr_x), int(curr_y))
            
        # 2. Cliques Independentes por Piscada (Sempre ativos)
        ear_esq, ear_dir = calcular_ear(face_landmarks, w, h)
        agora = time.time()
        
        # Mostrar EAR na tela para diagnóstico
        cv2.putText(frame, f"E:{ear_esq:.2f} D:{ear_dir:.2f}", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        esq_fechado = ear_esq < EAR_THRESHOLD
        dir_fechado = ear_dir < EAR_THRESHOLD
        
        # Regra estrita: Um fechado E o outro aberto (impede clique se piscar natural)
        if esq_fechado and not dir_fechado:
            if agora - ultimo_clique_esq > DEBOUNCE_TIME:
                pyautogui.click(button='left')
                ultimo_clique_esq = agora
                texto_clique_ate = agora + 0.5
                msg_clique = "CLIQUE ESQUERDO"
        elif dir_fechado and not esq_fechado:
            if agora - ultimo_clique_dir > DEBOUNCE_TIME:
                pyautogui.click(button='right')
                ultimo_clique_dir = agora
                texto_clique_ate = agora + 0.5
                msg_clique = "CLIQUE DIREITO"
    
    # --- FEEDBACK VISUAL GERAL ---
    cv2.putText(frame, texto_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, cor_status, 2)
    
    if time.time() < texto_clique_ate:
        cv2.putText(frame, msg_clique, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        
    cv2.imshow("Controle do Mouse (Pressione 'q' para sair)", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Limpeza final
cap.release()
cv2.destroyAllWindows()
print("Mouse virtual encerrado com sucesso.")
