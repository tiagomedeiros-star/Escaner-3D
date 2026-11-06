import os
from flask import Flask, request, jsonify, render_template
from lumaai import LumaAI

app = Flask(__name__)

# A chave será puxada das variáveis de ambiente da Vercel
LUMA_API_KEY = os.environ.get("LUMA_API_KEY")
client = LumaAI(auth_token=LUMA_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Nenhum vídeo enviado'}), 400
    
    video = request.files['video']
    
    # Salva na pasta /tmp (única permitida para gravação na Vercel)
    filepath = f"/tmp/temp_{video.filename}"
    video.save(filepath)

    try:
        # Envia para a Luma AI
        capture = client.captures.create(title="Scan de Suporte", video_path=filepath)
        os.remove(filepath) # Limpa a memória da Vercel
        
        return jsonify({'capture_id': capture.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<capture_id>', methods=['GET'])
def status(capture_id):
    try:
        capture = client.captures.get(id=capture_id)
        if capture.status == 'completed':
            return jsonify({'status': 'completed', 'model_url': capture.assets.obj})
        return jsonify({'status': capture.status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
