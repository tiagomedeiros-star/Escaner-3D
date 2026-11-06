import os
import base64
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Vai buscar a chave da Meshy às variáveis de ambiente da Vercel
MESHY_API_KEY = os.environ.get("MESHY_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {MESHY_API_KEY}",
    "Content-Type": "application/json"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem enviada'}), 400
    
    image = request.files['image']
    
    try:
        # A Meshy aceita o upload direto convertendo a imagem para formato base64
        image_data = image.read()
        base64_encoded = base64.b64encode(image_data).decode('utf-8')
        mime_type = image.mimetype or 'image/jpeg'
        data_uri = f"data:{mime_type};base64,{base64_encoded}"
        
        payload = {
            "image_url": data_uri,
            "enable_pbr": True # Ativa texturas realistas
        }
        
        # 1. Pede à Meshy para gerar o modelo 3D
        res = requests.post(
            "https://api.meshy.ai/v1/image-to-3d",
            headers=HEADERS,
            json=payload
        )
        data = res.json()
        
        if res.status_code not in [200, 202]:
            return jsonify({'error': f"Erro na Meshy: {data}"}), 500
            
        task_id = data.get("result")
        
        return jsonify({'capture_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<capture_id>', methods=['GET'])
def status(capture_id):
    try:
        # 2. Pergunta à Meshy se o modelo já está pronto
        res = requests.get(
            f"https://api.meshy.ai/v1/image-to-3d/{capture_id}",
            headers=HEADERS
        )
        data = res.json()
        
        estado = data.get("status", "").upper()
        
        if estado == "SUCCEEDED":
            model_urls = data.get("model_urls", {})
            # A Meshy devolve GLB (perfeito para web) ou OBJ. Vamos dar prioridade ao OBJ.
            model_url = model_urls.get("obj") or model_urls.get("glb") or ""
            return jsonify({'status': 'completed', 'model_url': model_url})
            
        elif estado in ["FAILED", "EXPIRED", "CANCELED"]:
            return jsonify({'status': 'failed'})
            
        return jsonify({'status': estado.replace('IN_PROGRESS', 'PROCESSANDO')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
