import cv2
import numpy as np

def testar_camera():
    print("=== TESTE SIMPLES DE CAMERA ===")
    print("Tentando acessar as cameras locais (DroidCam via USB costuma ser 0 ou 1)...\n")
    
    # Testar indices 0, 1 e 2
    for indice in range(3):
        print(f"Tentando abrir camera no indice {indice}...")
        
        # Tentar com backend padrao primeiro (geralmente MSMF no Windows)
        cap = cv2.VideoCapture(indice)
        
        if not cap.isOpened():
            print(f"  -> Indice {indice} falhou ao abrir.")
            cap.release()
            continue
            
        # Ler alguns frames para descartar lixo inicial
        for _ in range(10):
            cap.read()
            
        ret, frame = cap.read()
        
        if not ret or frame is None:
            print(f"  -> Indice {indice} abriu, mas nao conseguiu ler a imagem.")
            cap.release()
            continue
            
        # Analisar o frame
        media_b, media_g, media_r = cv2.mean(frame)[:3]
        desvio = np.std(frame)
        print(f"  -> SUCESSO! Indice {indice} leu a imagem.")
        print(f"     Detalhes: BGR=({media_b:.0f},{media_g:.0f},{media_r:.0f}), Desvio={desvio:.1f}")
        
        if desvio < 5.0:
            print("     AVISO: Imagem parece preta ou congelada.")
        elif media_g > 50 and media_b < 30 and media_r < 30:
            print("     AVISO: Imagem parece ser a famosa 'tela verde'.")
        
        print("\n=> Mostrando a imagem em uma janela. Pressione 'q' na janela para fechar e tentar a proxima, ou 'ESC' para sair do teste.")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Erro ao ler frame em tempo real.")
                break
                
            cv2.imshow(f"Teste de Camera - Indice {indice}", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == 27: # ESC
                cap.release()
                cv2.destroyAllWindows()
                return
                
        cap.release()
        cv2.destroyAllWindows()
        print("\nPassando para a proxima camera...\n")

    print("Fim do teste.")

if __name__ == "__main__":
    testar_camera()
