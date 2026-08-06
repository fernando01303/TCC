import urllib.request
import cv2
import numpy as np

ip = '192.168.1.3'
port = 4747

# Testar captura de screenshot individual via API do DroidCam
endpoints = [
    '/shot.jpg', '/photo.jpg', '/snapshot',
    '/v1/camera/snapshot', '/cam/1/frame.jpg',
    '/photo', '/capture', '/frame',
]

# Tambem testar o /video como stream binario (nao HTML)
print("Testando captura de frames do DroidCam...\n")

# Primeiro: tentar ler /video como stream MJPEG via OpenCV (nao urllib)
print("=== Teste OpenCV com URL /video ===")
for path in ['/video', '/videofeed']:
    url = f'http://{ip}:{port}{path}'
    print(f'Testando cv2.VideoCapture({url})...')
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap.isOpened():
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        if ret and frame is not None:
            m = cv2.mean(frame)[:3]
            d = np.std(frame)
            print(f'  SUCESSO! shape={frame.shape}, BGR=({m[0]:.0f},{m[1]:.0f},{m[2]:.0f}), std={d:.1f}')
            verde = m[1] > 50 and m[0] < 30 and m[2] < 30
            print(f'  Tela verde: {verde}')
        else:
            print(f'  Abriu mas nao leu frames')
        cap.release()
    else:
        print(f'  Nao abriu')

# Segundo: captura de screenshots via HTTP
print("\n=== Teste Screenshot HTTP ===")
for path in endpoints:
    url = f'http://{ip}:{port}{path}'
    try:
        req = urllib.request.urlopen(url, timeout=3)
        ct = req.headers.get('Content-Type', 'N/A')
        data = req.read(5000)
        is_jpeg = data[:2] == b'\xff\xd8'
        is_png = data[:4] == b'\x89PNG'
        print(f'{path:30s} -> Type: {ct}, Size: {len(data)}, JPEG: {is_jpeg}, PNG: {is_png}')
        if is_jpeg or is_png:
            print(f'  >>> ENCONTRADO ENDPOINT DE IMAGEM! <<<')
    except Exception as e:
        ecode = str(e)[:60]
        print(f'{path:30s} -> {ecode}')

print("\nTeste concluido.")
