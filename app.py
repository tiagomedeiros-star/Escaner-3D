import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Puxa a chave da Tripo AI das variáveis da Vercel
TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {TRIPO_API_KEY}"
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
        # 1. Faz o upload da imagem para os servidores da Tripo
        upload_res = requests.post(
            "https://api.tripo3d.ai/v2/openapi/upload",
            headers=HEADERS,
            files={"file": (image.filename, image.stream, image.mimetype)}
        )
        upload_data = upload_res.json()
        
        if upload_data.get("code") != 0:
            return jsonify({'error': f"Erro no upload: {upload_data}"}), 500
            
        image_token = upload_data["data"]["image_token"]
        
        # 2. Pede à IA para criar o modelo 3D a partir da imagem
        task_res = requests.post(
            "https://api.tripo3d.ai/v2/openapi/task",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "type": "image_to_model",
                "file": {
                    "type": "jpg",
                    "file_token": image_token
                }
            }
        )
        task_data = task_res.json()
        
        if task_data.get("code") != 0:
            return jsonify({'error': f"Erro na tarefa: {task_data}"}), 500
            
        return jsonify({'capture_id': task_data["data"]["task_id"]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<capture_id>', methods=['GET'])
def status(capture_id):
    try:
        res = requests.get(
            f"https://api.tripo3d.ai/v2/openapi/task/{capture_id}",
            headers=HEADERS
        )
        data = res.json()
        
        if data.get("code") != 0:
            return jsonify({'error': 'Erro ao consultar status'}), 500
            
        estado = data["data"]["status"].lower()
        
        if estado == "success":
            # A Tripo devolve o modelo principal pronto para download
            model_url = data["data"]["result"]["model"]["url"]
            return jsonify({'status': 'completed', 'model_url': model_url})
            
        elif estado in ["failed", "cancelled"]:
            return jsonify({'status': 'failed'})
            
        return jsonify({'status': estado})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
