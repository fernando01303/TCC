# Instalação das bibliotecas necessárias:
# pip install -r requirements.txt
#
# CONSULTAR: README.md antes de alterar este arquivo.

import ctypes
import functools
import math
import queue
import sys
import threading
import time
import tkinter as tk

import cv2
import mediapipe as mp
import pyautogui
import pyperclip
import pystray
import speech_recognition as sr
from PIL import Image, ImageDraw

# Forçar flush imediato de todo print() para que os logs apareçam em tempo real
print = functools.partial(print, flush=True)

# Desabilitar o failsafe do pyautogui para evitar crash se o mouse for para os cantos.
pyautogui.FAILSAFE = False
# Remover o atraso padrão de 0.1s entre comandos do PyAutoGUI (deixa o movimento suave)
pyautogui.PAUSE = 0

WINDOW_NAME = "Controle do Mouse ('h'=Ocultar, 'q'=Sair)"

# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

EMA_ALPHA = 0.35              # Suavização do nariz (menor = mais suave, maior = mais rápido)
DEADZONE_RADIUS = 15          # Raio em pixels da zona neutra ao redor da âncora
PINCA_THRESHOLD = 30          # Distância máxima em pixels para gestos auxiliares (médio, anelar, mindinho)
PINCA_EMBREAGEM_THRESHOLD = 15  # Distância quase zero para ativar/liberar a embreagem (polegar + indicador)

SENSIBILIDADE_INICIAL = 35.0
SENSIBILIDADE_MIN = 10.0
SENSIBILIDADE_MAX = 80.0
SENSIBILIDADE_PASSO = 5.0
GESTO_DEBOUNCE = 0.6          # Intervalo mínimo (s) entre ajustes de sensibilidade

EAR_THRESHOLD = 0.20          # Limiar de abertura do olho para detectar piscada
DEBOUNCE_CLIQUE = 0.8         # Intervalo mínimo (s) entre cliques do mesmo olho

VOZ_DEBOUNCE = 1.5            # Intervalo mínimo (s) após finalizar uma captura de voz


# =====================================================================
# OVERLAY FLUTUANTE (TOAST OSD SEM ROUBAR FOCO)
# =====================================================================

class OverlayToast:
    """
    Exibe mensagens flutuantes discretas no topo da tela mesmo quando a
    janela da câmera está oculta em segundo plano, sem roubar o foco.
    """

    def __init__(self):
        self._fila: queue.Queue = queue.Queue()
        self._pronto = threading.Event()
        self._thread = threading.Thread(target=self._executar_tk, daemon=True)
        self._thread.start()
        self._pronto.wait(timeout=2.0)

    def _aplicar_estilo_sem_foco(self, root: tk.Tk):
        """Aplica WS_EX_NOACTIVATE e WS_EX_TOOLWINDOW no Windows."""
        try:
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if not hwnd:
                hwnd = root.winfo_id()
            estilo = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, estilo | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

    def _executar_tk(self):
        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.90)
        root.configure(bg="#111827")

        label = tk.Label(
            root,
            text="",
            font=("Segoe UI", 13, "bold"),
            fg="#F9FAFB",
            bg="#111827",
            padx=20,
            pady=10,
        )
        label.pack()

        root.update_idletasks()
        self._aplicar_estilo_sem_foco(root)
        self._pronto.set()

        timer_id = {"id": None}
        anim_id = {"id": None}
        anim_estado = {"ativo": False, "texto_base": "", "passo": 0}
        frames_spinner = ["|", "/", "-", "\\"]

        def _esconder():
            timer_id["id"] = None
            root.withdraw()

        def _parar_animacao():
            anim_estado["ativo"] = False
            if anim_id["id"] is not None:
                root.after_cancel(anim_id["id"])
                anim_id["id"] = None

        def _posicionar_e_exibir():
            root.update_idletasks()
            largura = root.winfo_reqwidth()
            tela_w = root.winfo_screenwidth()
            pos_x = max(10, (tela_w - largura) // 2)
            root.geometry(f"+{pos_x}+24")
            root.deiconify()
            root.lift()

        def _animar_carregamento():
            if not anim_estado["ativo"]:
                return
            passo = anim_estado["passo"]
            pontos = "." * ((passo % 3) + 1)
            spinner = frames_spinner[passo % len(frames_spinner)]
            barra_len = 12
            pos_barra = passo % barra_len
            barra = "".join("■" if i == pos_barra else "·" for i in range(barra_len))
            label.config(
                text=f"{spinner} {anim_estado['texto_base']}{pontos}  [{barra}]",
                fg="#38BDF8",
            )
            _posicionar_e_exibir()
            anim_estado["passo"] += 1
            anim_id["id"] = root.after(140, _animar_carregamento)

        def _processar_fila():
            try:
                while True:
                    acao = self._fila.get_nowait()
                    if acao is None:
                        _parar_animacao()
                        root.destroy()
                        return

                    tipo = acao[0]
                    if tipo == "LOADING_START":
                        if timer_id["id"] is not None:
                            root.after_cancel(timer_id["id"])
                            timer_id["id"] = None
                        anim_estado["ativo"] = True
                        anim_estado["texto_base"] = acao[1]
                        anim_estado["passo"] = 0
                        _animar_carregamento()
                    elif tipo == "LOADING_STOP":
                        _parar_animacao()
                        _esconder()
                    else:
                        _parar_animacao()
                        _, texto, cor_fg, duracao = acao
                        label.config(text=texto, fg=cor_fg)
                        _posicionar_e_exibir()

                        if timer_id["id"] is not None:
                            root.after_cancel(timer_id["id"])
                        timer_id["id"] = root.after(int(duracao * 1000), _esconder)
            except queue.Empty:
                pass
            root.after(50, _processar_fila)

        root.after(50, _processar_fila)
        root.mainloop()

    def iniciar_carregamento(self, texto_base: str = "Software sendo iniciado"):
        self._fila.put(("LOADING_START", texto_base))

    def parar_carregamento(self):
        self._fila.put(("LOADING_STOP",))

    def mostrar(self, texto: str, cor_fg: str = "#F9FAFB", duracao: float = 2.0):
        self._fila.put(("MSG", texto, cor_fg, duracao))

    def encerrar(self):
        self._fila.put(None)


def fechar_pyi_splash():
    """Fecha a splash screen nativa do PyInstaller, caso esteja rodando como .exe."""
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


def mostrar_alerta_erro(titulo: str, mensagem: str):
    """Exibe caixa de diálogo nativa do Windows (funciona sem janela de terminal)."""
    try:
        ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 0x10)
    except Exception:
        print(f"{titulo}: {mensagem}")


# =====================================================================
# BANDEJA DO SISTEMA (SYSTEM TRAY)
# =====================================================================

def criar_icone_bandeja():
    """Gera um ícone simples em memória para a bandeja do Windows."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(17, 24, 39, 255), outline=(56, 189, 248, 255), width=4)
    draw.ellipse((22, 22, 42, 42), fill=(34, 197, 94, 255))
    return img


# =====================================================================
# FUNÇÕES AUXILIARES DE VISÃO E MOUSE
# =====================================================================

def abrir_camera_com_timeout(indice: int, timeout: float = 5.0):
    """
    Abre uma câmera em thread separada para evitar travamento indefinido
    do cv2.VideoCapture no Windows (ver BUG #4 e BUG #6 no README.md).
    """
    resultado = {"cap": None}

    def _tentar_abrir():
        temp_cap = cv2.VideoCapture(indice)
        if not temp_cap.isOpened():
            temp_cap.release()
            return

        # Descartar frames iniciais corrompidos
        for _ in range(10):
            temp_cap.read()

        ret, frame = temp_cap.read()
        if not ret or frame is None:
            temp_cap.release()
            return

        resultado["cap"] = temp_cap

    thread = threading.Thread(target=_tentar_abrir, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        print(f"  -> Indice {indice} excedeu o tempo limite ({timeout}s).")
        return None

    return resultado["cap"]


def inicializar_camera():
    """Tenta conectar nas câmeras locais (índices 0, 1, 2)."""
    print("\n=== INICIALIZACAO DA CAMERA ===\n")
    print("Tentando acessar as cameras locais (DroidCam via USB costuma ser 0 ou 1)...\n")

    for indice in range(3):
        print(f"Tentando abrir camera no indice {indice}...")
        cap = abrir_camera_com_timeout(indice, timeout=5.0)
        if cap is not None:
            print(f"  -> SUCESSO! Camera conectada no indice {indice}.\n")
            return cap
        print(f"  -> Indice {indice} indisponivel.")

    return None


def calcular_distancia(p1, p2, w: int, h: int) -> float:
    """Calcula a distância euclidiana em pixels entre dois landmarks normalizados."""
    x1, y1 = p1.x * w, p1.y * h
    x2, y2 = p2.x * w, p2.y * h
    return math.hypot(x2 - x1, y2 - y1)


def calcular_ear(face_landmarks, w: int, h: int):
    """
    Calcula o Eye Aspect Ratio (EAR) — Proporção de Abertura do Olho.
    Retorna os valores separados para olho esquerdo e direito.
    """
    # Olho esquerdo — cantos horizontais (33, 133), vertical (159 superior, 145 inferior)
    dist_h_esq = calcular_distancia(face_landmarks.landmark[33], face_landmarks.landmark[133], w, h)
    dist_v_esq = calcular_distancia(face_landmarks.landmark[159], face_landmarks.landmark[145], w, h)
    ear_esq = dist_v_esq / dist_h_esq if dist_h_esq != 0 else 0.0

    # Olho direito — cantos horizontais (362, 263), vertical (386 superior, 374 inferior)
    dist_h_dir = calcular_distancia(face_landmarks.landmark[362], face_landmarks.landmark[263], w, h)
    dist_v_dir = calcular_distancia(face_landmarks.landmark[386], face_landmarks.landmark[374], w, h)
    ear_dir = dist_v_dir / dist_h_dir if dist_h_dir != 0 else 0.0

    return ear_esq, ear_dir


def colar_texto_seguro(texto: str):
    """Copia para a área de transferência e cola via Ctrl+V para preservar acentos em PT-BR."""
    pyperclip.copy(texto)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")


# =====================================================================
# ESTADO DA CAPTURA DE VOZ (THREAD-SAFE)
# =====================================================================

voz_lock = threading.Lock()
voz_estado = {
    "ativa": False,
    "mensagem": "",
    "cor": (255, 255, 0),
    "ate": 0.0,
    "ultimo_fim": 0.0,
}


def definir_feedback_voz(
    mensagem: str,
    cor=(255, 255, 0),
    duracao: float = 2.5,
    ativa: bool = False,
    toast: OverlayToast = None,
    cor_toast: str = "#F9FAFB",
):
    with voz_lock:
        voz_estado["ativa"] = ativa
        voz_estado["mensagem"] = mensagem
        voz_estado["cor"] = cor
        voz_estado["ate"] = time.time() + duracao if duracao > 0 else 0.0
        if not ativa:
            voz_estado["ultimo_fim"] = time.time()

    if toast is not None and mensagem:
        toast.mostrar(mensagem, cor_fg=cor_toast, duracao=duracao)


def worker_voz(toast: OverlayToast):
    """Executa a escuta do microfone e transcrição em segundo plano sem travar o vídeo."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            definir_feedback_voz(
                "Ouvindo...",
                cor=(0, 255, 255),
                duracao=12.0,
                ativa=True,
                toast=toast,
                cor_toast="#FACC15",
            )
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

        definir_feedback_voz(
            "Processando voz...",
            cor=(255, 200, 0),
            duracao=5.0,
            ativa=True,
            toast=toast,
            cor_toast="#38BDF8",
        )
        texto = recognizer.recognize_google(audio, language="pt-BR")
        comando = texto.strip().lower()
        print(f"[VOZ] Texto reconhecido: {texto}")

        if comando in ("apagar", "apaga"):
            pyautogui.hotkey("ctrl", "backspace")
            definir_feedback_voz(
                "Palavra apagada",
                cor=(0, 200, 255),
                duracao=2.0,
                ativa=False,
                toast=toast,
                cor_toast="#38BDF8",
            )
        elif comando in ("espaço", "espaco"):
            pyautogui.press("space")
            definir_feedback_voz(
                "Espaço inserido",
                cor=(0, 200, 255),
                duracao=2.0,
                ativa=False,
                toast=toast,
                cor_toast="#38BDF8",
            )
        else:
            colar_texto_seguro(texto)
            definir_feedback_voz(
                f"Digitado: {texto[:28]}",
                cor=(0, 255, 0),
                duracao=2.5,
                ativa=False,
                toast=toast,
                cor_toast="#4ADE80",
            )

    except (sr.WaitTimeoutError, sr.UnknownValueError):
        definir_feedback_voz(
            "Nenhuma fala identificada",
            cor=(0, 165, 255),
            duracao=2.2,
            ativa=False,
            toast=toast,
            cor_toast="#FB923C",
        )
    except sr.RequestError:
        definir_feedback_voz(
            "Erro de internet na voz",
            cor=(0, 0, 255),
            duracao=2.5,
            ativa=False,
            toast=toast,
            cor_toast="#F87171",
        )
    except OSError:
        definir_feedback_voz(
            "Microfone nao encontrado",
            cor=(0, 0, 255),
            duracao=2.5,
            ativa=False,
            toast=toast,
            cor_toast="#F87171",
        )
    except Exception as exc:
        print(f"[VOZ] Erro inesperado: {exc}")
        definir_feedback_voz(
            "Erro na captura de voz",
            cor=(0, 0, 255),
            duracao=2.5,
            ativa=False,
            toast=toast,
            cor_toast="#F87171",
        )


def iniciar_captura_voz(toast: OverlayToast):
    """Dispara a thread de voz se não houver outra em andamento e respeitar o debounce."""
    with voz_lock:
        if voz_estado["ativa"]:
            return False
        if time.time() - voz_estado["ultimo_fim"] < VOZ_DEBOUNCE:
            return False
        voz_estado["ativa"] = True

    threading.Thread(target=worker_voz, args=(toast,), daemon=True).start()
    return True


# =====================================================================
# INICIALIZAÇÃO PRINCIPAL
# =====================================================================

def main():
    toast = OverlayToast()
    fechar_pyi_splash()
    toast.iniciar_carregamento("Software sendo iniciado")

    screen_w, screen_h = pyautogui.size()
    print(f"Resolucao da tela detectada: {screen_w}x{screen_h}")

    # Configuração do MediaPipe Face Mesh e Hands (usar mediapipe < 1.0, ver BUG #2)
    face_mesh = mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    hands = mp.solutions.hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = inicializar_camera()
    toast.parar_carregamento()
    if cap is None:
        toast.encerrar()
        mostrar_alerta_erro(
            "Mouse Virtual - Erro de Câmera",
            "Nenhuma câmera válida foi encontrada.\n\n"
            "Verifique se a webcam ou o DroidCam (cabo USB) está aberto e ativo.",
        )
        sys.exit(1)

    toast.mostrar("Mouse Virtual ativo!", "#4ADE80", 2.0)

    # Controle de execução e visibilidade da janela (para rodar em segundo plano)
    app_estado = {"mostrar_camera": True, "encerrar": False}
    janela_aberta = False

    def _alternar_camera(icon, item):
        app_estado["mostrar_camera"] = not app_estado["mostrar_camera"]

    def _sair_app(icon, item):
        app_estado["encerrar"] = True

    tray_icon = pystray.Icon(
        "MouseVirtual",
        criar_icone_bandeja(),
        "Mouse Virtual (TCC)",
        menu=pystray.Menu(
            pystray.MenuItem("Mostrar / Ocultar Câmera", _alternar_camera, default=True),
            pystray.MenuItem("Sair", _sair_app),
        ),
    )
    tray_icon.run_detached()

    # Estado do Joystick e Suavização
    curr_x, curr_y = screen_w / 2, screen_h / 2
    pyautogui.moveTo(int(curr_x), int(curr_y))
    joystick_speed = SENSIBILIDADE_INICIAL

    nariz_suave_x, nariz_suave_y = None, None
    ancora_x, ancora_y = None, None

    # Controle de Cliques e Gestos
    ultimo_clique_esq = time.time()
    ultimo_clique_dir = time.time()
    ultimo_ajuste_sens = 0.0
    texto_clique_ate = 0.0
    msg_clique = ""

    print("=== MOUSE VIRTUAL INICIADO ===")
    print("Polegar + Indicador : Mover o mouse (Embreagem)")
    print("Polegar + Medio     : Aumentar sensibilidade")
    print("Polegar + Anelar    : Diminuir sensibilidade")
    print("Polegar + Mindinho  : Ativar ditado por voz (PT-BR)")
    print("Piscar um olho      : Clique Esquerdo / Direito")
    print("Fechar janela / 'h' : Continuar em segundo plano (bandeja)")
    print("Pressione 'q'       : Encerrar aplicativo.\n")

    try:
        while not app_estado["encerrar"]:
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Espelhar horizontalmente (interação tipo espelho)
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results_face = face_mesh.process(rgb_frame)
            results_hands = hands.process(rgb_frame)

            texto_status = "Mouse Pausado (Polegar+Indicador)"
            cor_status = (0, 0, 255)
            embreagem_ativa = False
            agora = time.time()

            # --- GESTOS DA MÃO (EMBREAGEM, SENSIBILIDADE E VOZ) ---
            if results_hands.multi_hand_landmarks:
                hand_landmarks = results_hands.multi_hand_landmarks[0]
                polegar = hand_landmarks.landmark[4]
                indicador = hand_landmarks.landmark[8]
                medio = hand_landmarks.landmark[12]
                anelar = hand_landmarks.landmark[16]
                mindinho = hand_landmarks.landmark[20]

                dist_indicador = calcular_distancia(polegar, indicador, w, h)
                dist_medio = calcular_distancia(polegar, medio, w, h)
                dist_anelar = calcular_distancia(polegar, anelar, w, h)
                dist_mindinho = calcular_distancia(polegar, mindinho, w, h)

                if app_estado["mostrar_camera"]:
                    px, py = int(polegar.x * w), int(polegar.y * h)
                    ix, iy = int(indicador.x * w), int(indicador.y * h)
                    mx, my = int(medio.x * w), int(medio.y * h)
                    ax, ay = int(anelar.x * w), int(anelar.y * h)
                    kx, ky = int(mindinho.x * w), int(mindinho.y * h)

                    cor_pinca = (0, 255, 0) if dist_indicador < PINCA_EMBREAGEM_THRESHOLD else (0, 0, 255)
                    cv2.line(frame, (px, py), (ix, iy), cor_pinca, 2)
                    cv2.circle(frame, (px, py), 5, cor_pinca, -1)
                    cv2.circle(frame, (ix, iy), 5, cor_pinca, -1)
                    cv2.circle(frame, (mx, my), 4, (255, 200, 0), -1)
                    cv2.circle(frame, (ax, ay), 4, (255, 140, 0), -1)
                    cv2.circle(frame, (kx, ky), 4, (255, 0, 255), -1)

                if dist_indicador < PINCA_EMBREAGEM_THRESHOLD:
                    embreagem_ativa = True
                    texto_status = "Mouse ATIVO"
                    cor_status = (0, 255, 0)
                elif dist_medio < PINCA_THRESHOLD:
                    if app_estado["mostrar_camera"]:
                        cv2.line(frame, (px, py), (mx, my), (0, 255, 255), 2)
                    if agora - ultimo_ajuste_sens > GESTO_DEBOUNCE:
                        joystick_speed = min(SENSIBILIDADE_MAX, joystick_speed + SENSIBILIDADE_PASSO)
                        ultimo_ajuste_sens = agora
                        texto_clique_ate = agora + 0.6
                        msg_clique = f"SENSIBILIDADE: {int(joystick_speed)}"
                        toast.mostrar(f"Sensibilidade: {int(joystick_speed)}", "#38BDF8", 1.8)
                elif dist_anelar < PINCA_THRESHOLD:
                    if app_estado["mostrar_camera"]:
                        cv2.line(frame, (px, py), (ax, ay), (0, 165, 255), 2)
                    if agora - ultimo_ajuste_sens > GESTO_DEBOUNCE:
                        joystick_speed = max(SENSIBILIDADE_MIN, joystick_speed - SENSIBILIDADE_PASSO)
                        ultimo_ajuste_sens = agora
                        texto_clique_ate = agora + 0.6
                        msg_clique = f"SENSIBILIDADE: {int(joystick_speed)}"
                        toast.mostrar(f"Sensibilidade: {int(joystick_speed)}", "#38BDF8", 1.8)
                elif dist_mindinho < PINCA_THRESHOLD:
                    if app_estado["mostrar_camera"]:
                        cv2.line(frame, (px, py), (kx, ky), (255, 0, 255), 2)
                    iniciar_captura_voz(toast)

            # --- MOVIMENTAÇÃO SUAVIZADA E CLIQUES (ROSTO) ---
            if results_face.multi_face_landmarks:
                face_landmarks = results_face.multi_face_landmarks[0]

                nariz = face_landmarks.landmark[1]
                raw_x = nariz.x * w
                raw_y = nariz.y * h

                # Filtro EMA para eliminar micro-tremores do rosto/câmera
                if nariz_suave_x is None:
                    nariz_suave_x, nariz_suave_y = raw_x, raw_y
                else:
                    nariz_suave_x = EMA_ALPHA * raw_x + (1.0 - EMA_ALPHA) * nariz_suave_x
                    nariz_suave_y = EMA_ALPHA * raw_y + (1.0 - EMA_ALPHA) * nariz_suave_y

                # Âncora Dinâmica: segue o nariz enquanto a embreagem está solta
                if not embreagem_ativa or ancora_x is None:
                    ancora_x, ancora_y = nariz_suave_x, nariz_suave_y

                if app_estado["mostrar_camera"]:
                    nariz_x = int(round(nariz_suave_x))
                    nariz_y = int(round(nariz_suave_y))
                    ancora_px = int(round(ancora_x))
                    ancora_py = int(round(ancora_y))

                    cor_deadzone = (0, 255, 0) if embreagem_ativa else (0, 0, 255)
                    cv2.circle(frame, (ancora_px, ancora_py), DEADZONE_RADIUS, cor_deadzone, 2)
                    cv2.circle(frame, (nariz_x, nariz_y), 5, (255, 0, 0), -1)
                    cv2.line(frame, (ancora_px, ancora_py), (nariz_x, nariz_y), (255, 255, 255), 1)

                if embreagem_ativa:
                    dx = nariz_suave_x - ancora_x
                    dy = nariz_suave_y - ancora_y
                    dist_centro = math.hypot(dx, dy)

                    if dist_centro > DEADZONE_RADIUS:
                        intensidade = (dist_centro - DEADZONE_RADIUS) / (w / 2)
                        vel_x = (dx / dist_centro) * intensidade * joystick_speed
                        vel_y = (dy / dist_centro) * intensidade * joystick_speed

                        curr_x = max(0.0, min(float(screen_w), curr_x + vel_x))
                        curr_y = max(0.0, min(float(screen_h), curr_y + vel_y))

                        pyautogui.moveTo(int(curr_x), int(curr_y))

                # Cliques independentes por piscada (sempre ativos)
                ear_esq, ear_dir = calcular_ear(face_landmarks, w, h)
                if app_estado["mostrar_camera"]:
                    cv2.putText(
                        frame,
                        f"E:{ear_esq:.2f} D:{ear_dir:.2f}",
                        (10, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 0),
                        2,
                    )

                esq_fechado = ear_esq < EAR_THRESHOLD
                dir_fechado = ear_dir < EAR_THRESHOLD

                if esq_fechado and not dir_fechado:
                    if agora - ultimo_clique_esq > DEBOUNCE_CLIQUE:
                        pyautogui.click(button="left")
                        ultimo_clique_esq = agora
                        texto_clique_ate = agora + 0.5
                        msg_clique = "CLIQUE ESQUERDO"
                elif dir_fechado and not esq_fechado:
                    if agora - ultimo_clique_dir > DEBOUNCE_CLIQUE:
                        pyautogui.click(button="right")
                        ultimo_clique_dir = agora
                        texto_clique_ate = agora + 0.5
                        msg_clique = "CLIQUE DIREITO"

            # --- EXIBIÇÃO DA JANELA DA CÂMERA (OU SEGUNDO PLANO) ---
            if app_estado["mostrar_camera"]:
                cv2.putText(frame, texto_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, cor_status, 2)
                cv2.putText(
                    frame,
                    f"Sensibilidade: {int(joystick_speed)}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )

                if agora < texto_clique_ate:
                    cv2.putText(frame, msg_clique, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)

                with voz_lock:
                    voz_msg = voz_estado["mensagem"]
                    voz_cor = voz_estado["cor"]
                    voz_visivel = voz_estado["ativa"] or (agora < voz_estado["ate"])

                if voz_visivel and voz_msg:
                    cv2.putText(frame, voz_msg, (10, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, voz_cor, 2)

                cv2.imshow(WINDOW_NAME, frame)
                janela_aberta = True

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    app_estado["encerrar"] = True
                elif key == ord("h"):
                    app_estado["mostrar_camera"] = False
                    toast.mostrar("Rodando em segundo plano (bandeja)", "#A5B4FC", 2.0)
                elif key in (ord("+"), ord("=")):
                    joystick_speed = min(SENSIBILIDADE_MAX, joystick_speed + SENSIBILIDADE_PASSO)
                    toast.mostrar(f"Sensibilidade: {int(joystick_speed)}", "#38BDF8", 1.8)
                elif key in (ord("-"), ord("_")):
                    joystick_speed = max(SENSIBILIDADE_MIN, joystick_speed - SENSIBILIDADE_PASSO)
                    toast.mostrar(f"Sensibilidade: {int(joystick_speed)}", "#38BDF8", 1.8)

                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    app_estado["mostrar_camera"] = False
                    janela_aberta = False
                    toast.mostrar("Rodando em segundo plano (bandeja)", "#A5B4FC", 2.0)
            else:
                if janela_aberta:
                    try:
                        cv2.destroyWindow(WINDOW_NAME)
                    except cv2.error:
                        pass
                    janela_aberta = False
                time.sleep(0.005)
    finally:
        try:
            tray_icon.stop()
        except Exception:
            pass
        toast.encerrar()
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()
        hands.close()
        print("Mouse virtual encerrado com sucesso.")


if __name__ == "__main__":
    main()
