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
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 1. Filtros melhorados para lidar com sombras e reflexos
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)
        
        # Margens mais amplas para apanhar objetos com menos contraste
        edged = cv2.Canny(gray, 30, 150)
        
        # Operação "Close" para unir linhas quebradas (fecha os contornos dos objetos)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)
        
        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Reduzimos a área mínima para apanhar objetos mesmo se a foto for tirada de longe
        valid_cnts = [c for c in cnts if cv2.contourArea(c) > 1000]
        
        # 2. MODO DEBUG: Se falhar, mostra o que a câmara viu
        if len(valid_cnts) < 2:
            cv2.putText(img, f"ERRO: Encontrou {len(valid_cnts)} objetos.", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(img, "Melhora o contraste ou remove as sombras.", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            # Desenha a vermelho tudo o que o algoritmo considerou ser um objeto
            cv2.drawContours(img, valid_cnts, -1, (0, 0, 255), 2)
            
            _, buffer = cv2.imencode('.jpg', img)
            img_b64 = base64.b64encode(buffer).decode('utf-8')
            return jsonify({'image_url': f"data:image/jpeg;base64,{img_b64}"})
            
        # 3. Ordenar da Esquerda (Cartão) para a Direita (Peça)
        valid_cnts = sorted(valid_cnts, key=lambda c: cv2.boundingRect(c)[0])
        
        ref_x, ref_y, ref_w, ref_h = cv2.boundingRect(valid_cnts[0])
        pixels_por_milimetro = ref_w / 85.6
        
        for c in valid_cnts:
            x, y, w, h = cv2.boundingRect(c)
            
            largura_mm = w / pixels_por_milimetro
            altura_mm = h / pixels_por_milimetro
            
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            texto = f"{largura_mm:.1f} x {altura_mm:.1f} mm"
            cv2.putText(img, texto, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        _, buffer = cv2.imencode('.jpg', img)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({'image_url': f"data:image/jpeg;base64,{img_b64}"})
        
    except Exception as e:
        return jsonify({'error': f"Erro a processar imagem: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
