import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

LUMA_API_KEY = os.environ.get("LUMA_API_KEY")

# Formato de autenticação exato exigido pela API de Captura 3D clássica
HEADERS = {
    "Authorization": f"luma-api-key {LUMA_API_KEY}"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Nenhum vídeo enviado'}), 400
    
    video = request.files['video']
    
    try:
        # 1. Pede à Luma para criar um projeto e gerar um link seguro de upload
        url_response = requests.post(
            "https://api.lumalabs.ai/api/v2/capture", 
            headers=HEADERS, 
            data={"title": "Scan de Suporte"}
        )
        url_data = url_response.json()
        
        if 'uploadUrl' not in url_data:
            # Se a Luma recusar, devolve o erro real da Luma para o ecrã
            return jsonify({'error': f"Resposta da Luma: {url_data}"}), 500
            
        upload_url = url_data['uploadUrl']
        capture_id = url_data['slug']
        
        # 2. Faz o upload direto do vídeo em memória para o link seguro recebido
        requests.put(
            upload_url, 
            data=video.read(), 
            headers={"Content-Type": "video/webm"}
        )
        
        # 3. Dá o comando à Luma para iniciar o processamento 3D do vídeo enviado
        requests.post(
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
            # Procura o link do ficheiro 3D (.obj ou .zip) nos resultados
            artifacts = data.get('latestRun', {}).get('artifacts', []) or data.get('artifacts', [])
            for artifact in artifacts:
                url = artifact.get('url', '')
                if url.endswith('.obj') or url.endswith('.zip'):
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
