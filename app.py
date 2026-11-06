import cv2
import numpy as np
import base64
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Medidas reais de uma folha A4 em milímetros
A4_LARGURA_MM = 210.0
A4_ALTURA_MM = 297.0

def ordenar_pontos(pts):
    # Organiza os 4 cantos da folha: superior-esquerdo, superior-direito, inferior-direito, inferior-esquerdo
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem enviada'}), 400

    image_file = request.files['image']
    image_bytes = image_file.read()

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 1. Preparação da imagem para encontrar a folha A4
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 50, 150)

        # 2. Procura pelo contorno da folha A4 (o maior retângulo com 4 cantos)
        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)

        folha_cnt = None
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(c) > 10000:
                folha_cnt = approx
                break

        if folha_cnt is None:
            return jsonify({'error': 'Não foi possível detetar a folha A4 inteira. Certifica-te de que os 4 cantos do papel aparecem na foto.'}), 400

        # 3. Correção de perspetiva da folha A4
        pts_origem = ordenar_pontos(folha_cnt.reshape(4, 2))
        
        # Define o tamanho da imagem retificada proporcional à folha A4 (escala: ~3 pixels por mm)
        largura_px = int(A4_LARGURA_MM * 3)
        altura_px = int(A4_ALTURA_MM * 3)
        
        pts_destino = np.array([
            [0, 0],
            [largura_px - 1, 0],
            [largura_px - 1, altura_px - 1],
            [0, altura_px - 1]
        ], dtype="float32")

        matriz = cv2.getPerspectiveTransform(pts_origem, pts_destino)
        folha_alinhada = cv2.warpPerspective(img, matriz, (largura_px, altura_px))

        # Fator de escala: pixels por milímetro
        px_por_mm = largura_px / A4_LARGURA_MM

        # 4. Detetar a peça mecânica dentro da folha retificada
        gray_folha = cv2.cvtColor(folha_alinhada, cv2.COLOR_BGR2GRAY)
        # Binarização inversa: a folha branca vira fundo preto e a peça escura vira branca
        _, thresh = cv2.threshold(gray_folha, 180, 255, cv2.THRESH_BINARY_INV)

        peca_cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pecas_validas = [c for c in peca_cnts if cv2.contourArea(c) > 500]

        if not pecas_validas:
            return jsonify({'error': 'Folha A4 detetada, mas nenhuma peça foi encontrada sobre ela.'}), 400

        # Seleciona a maior forma sobre a folha (a peça principal)
        peca_principal = max(pecas_validas, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(peca_principal)

        largura_mm = w / px_por_mm
        altura_mm = h / px_por_mm

        # 5. Desenhar o resultado com as cotas em milímetros
        cv2.rectangle(folha_alinhada, (x, y), (x + w, y + h), (0, 255, 0), 2)
        texto = f"{largura_mm:.1f} x {altura_mm:.1f} mm"
        cv2.putText(folha_alinhada, texto, (x, max(25, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        _, buffer = cv2.imencode('.jpg', folha_alinhada)
        img_b64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({'image_url': f"data:image/jpeg;base64,{img_b64}"})

    except Exception as e:
        return jsonify({'error': f"Erro de processamento: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
