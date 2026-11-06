import cv2
import numpy as np
import base64
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

A4_MENOR_MM = 210.0
A4_MAIOR_MM = 297.0

def ordenar_pontos(pts):
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

        # 1. Encontrar o contorno da folha A4
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 40, 140)

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
            return jsonify({'error': 'Cantos da folha A4 não encontrados. Enquadre todo o papel com contraste no fundo.'}), 400

        # 2. Correção de perspetiva da folha
        pts_origem = ordenar_pontos(folha_cnt.reshape(4, 2))
        (tl, tr, br, bl) = pts_origem

        largura_media = max(int(np.linalg.norm(tr - tl)), int(np.linalg.norm(br - bl)))
        altura_media = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))

        if largura_media > altura_media:
            largura_real_mm, altura_real_mm = A4_MAIOR_MM, A4_MENOR_MM
        else:
            largura_real_mm, altura_real_mm = A4_MENOR_MM, A4_MAIOR_MM

        px_por_mm = 3.0
        largura_px = int(largura_real_mm * px_por_mm)
        altura_px = int(altura_real_mm * px_por_mm)

        pts_destino = np.array([
            [0, 0],
            [largura_px - 1, 0],
            [largura_px - 1, altura_px - 1],
            [0, altura_px - 1]
        ], dtype="float32")

        matriz = cv2.getPerspectiveTransform(pts_origem, pts_destino)
        folha_alinhada = cv2.warpPerspective(img, matriz, (largura_px, altura_px))

        # 3. Recorte com margem interna de segurança (15 mm de borda descartada)
        margem_px = int(15 * px_por_mm)
        folha_util = folha_alinhada[margem_px:altura_px - margem_px, margem_px:largura_px - margem_px]

        # 4. Detetar a peça dentro da área útil
        gray_util = cv2.cvtColor(folha_util, cv2.COLOR_BGR2GRAY)
        blur_util = cv2.GaussianBlur(gray_util, (7, 7), 0)
        _, thresh = cv2.threshold(blur_util, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        peca_cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        area_total_util = folha_util.shape[0] * folha_util.shape[1]
        
        pecas_validas = [
            c for c in peca_cnts 
            if 1000 < cv2.contourArea(c) < (0.80 * area_total_util)
        ]

        if not pecas_validas:
            return jsonify({'error': 'A folha A4 foi identificada, mas a peça não foi destacada. Certifique-se de que a peça tem contraste contra o papel branco.'}), 400

        # Seleciona o maior objeto dentro da folha
        peca_principal = max(pecas_validas, key=cv2.contourArea)
        rect_girado = cv2.minAreaRect(peca_principal)
        (centro, (tam_1, tam_2), angulo) = rect_girado

        dim_a_mm = tam_1 / px_por_mm
        dim_b_mm = tam_2 / px_por_mm

        maior_dim = max(dim_a_mm, dim_b_mm)
        menor_dim = min(dim_a_mm, dim_b_mm)

        # Correção aqui: np.int32 em vez de np.int0
        box = cv2.boxPoints(rect_girado)
        box = box + np.array([margem_px, margem_px])
        box = np.int32(box)

        cv2.drawContours(folha_alinhada, [box], 0, (0, 255, 0), 3)

        cx, cy = int(centro[0] + margem_px), int(centro[1] + margem_px)
        texto = f"{maior_dim:.1f} x {menor_dim:.1f} mm"
        cv2.putText(folha_alinhada, texto, (cx - 80, max(40, cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        _, buffer = cv2.imencode('.jpg', folha_alinhada)
        img_b64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({'image_url': f"data:image/jpeg;base64,{img_b64}"})

    except Exception as e:
        return jsonify({'error': f"Falha no processamento: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
