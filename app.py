import cv2
import numpy as np
import base64
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

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
        # 1. Converter a foto recebida para o formato do OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 2. Processar a imagem para detetar bordas (escala de cinza, desfoque e Canny)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        edged = cv2.Canny(gray, 50, 100)
        edged = cv2.dilate(edged, None, iterations=1)
        edged = cv2.erode(edged, None, iterations=1)
        
        # 3. Encontrar os objetos (contornos) na imagem
        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Ignorar sujidade ou pequenos reflexos filtrando pelo tamanho da área
        valid_cnts = [c for c in cnts if cv2.contourArea(c) > 3000]
        
        if len(valid_cnts) < 2:
            return jsonify({'error': 'Não foram detetados 2 objetos claros. Usa um fundo liso (ex: folha branca).'}), 400
            
        # 4. Ordenar os objetos da Esquerda para a Direita
        valid_cnts = sorted(valid_cnts, key=lambda c: cv2.boundingRect(c)[0])
        
        # O objeto mais à esquerda (índice 0) deve ser o Cartão de Referência (85.6 mm)
        ref_x, ref_y, ref_w, ref_h = cv2.boundingRect(valid_cnts[0])
        pixels_por_milimetro = ref_w / 85.6
        
        # 5. Medir e desenhar retângulos verdes e os valores em mm
        for c in valid_cnts:
            x, y, w, h = cv2.boundingRect(c)
            
            largura_mm = w / pixels_por_milimetro
            altura_mm = h / pixels_por_milimetro
            
            # Desenha a caixa verde
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Escreve o texto com as medidas
            texto = f"{largura_mm:.1f} x {altura_mm:.1f} mm"
            cv2.putText(img, texto, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 6. Converter a imagem processada de volta para envio ao navegador
        _, buffer = cv2.imencode('.jpg', img)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({'image_url': f"data:image/jpeg;base64,{img_b64}"})
        
    except Exception as e:
        return jsonify({'error': f"Erro a processar imagem: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
