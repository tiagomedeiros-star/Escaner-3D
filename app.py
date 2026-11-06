import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

LUMA_API_KEY = os.environ.get("LUMA_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {LUMA_API_KEY}"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Nenhum vídeo enviado'}), 400
    
    video = request.files['video']
    
    # 1. Pede à Luma uma URL de upload assinada (Upload URL)
    try:
        url_response = requests.post(
            "https://api.lumalabs.ai/api/v2/capture/upload_url", 
            headers=HEADERS, 
            params={"title": "Scan de Suporte"}
        )
        url_data = url_response.json()
        
        if 'uploadUrl' not in url_data:
            return jsonify({'error': 'Falha ao obter URL de upload', 'details': url_data}), 500
            
        upload_url = url_data['uploadUrl']
        capture_id = url_data['slug']
        
        # 2. Faz o upload direto do vídeo em memória para o link recebido (sem guardar no disco da Vercel)
        upload_response = requests.put(
            upload_url, 
            data=video.read(), 
            headers={"Content-Type": "video/webm"}
        )
        
        # 3. Avisa a Luma para iniciar o processamento 3D
        trigger_response = requests.post(
            f"https://api.lumalabs.ai/api/v2/capture/{capture_id}/trigger", 
            headers=HEADERS
        )
        
        return jsonify({'capture_id': capture_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<capture_id>', methods=['GET'])
def status(capture_id):
    try:
        response = requests.get(
            f"https://api.lumalabs.ai/api/v2/capture/{capture_id}", 
            headers=HEADERS
        )
        data = response.json()
        
        estado = data.get('status', '').upper()
        
        if estado == "FINISHED":
            model_url = ""
            for artifact in data.get('artifacts', []):
                url = artifact.get('url', '')
                if '.obj' in url.lower() or '.zip' in url.lower():
                    model_url = url
                    break
            return jsonify({'status': 'completed', 'model_url': model_url})
            
        elif estado == "FAILED":
            return jsonify({'status': 'failed'})
            
        return jsonify({'status': estado})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
