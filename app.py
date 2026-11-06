import os
from flask import Flask, request, jsonify, render_template
from lumaapi import LumaClient

app = Flask(__name__)

# Puxa a chave da Vercel e inicializa a biblioteca clássica de 3D
LUMA_API_KEY = os.environ.get("LUMA_API_KEY")
client = LumaClient(LUMA_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Nenhum vídeo enviado'}), 400
    
    video = request.files['video']
    filepath = f"/tmp/temp_{video.filename}"
    video.save(filepath)

    try:
        # A API de Captura usa .submit() e retorna o ID (slug) da operação
        slug = client.submit(filepath, title="Scan de Suporte")
        os.remove(filepath) 
        
        return jsonify({'capture_id': slug})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<capture_id>', methods=['GET'])
def status(capture_id):
    try:
        # Consulta o status atual do processamento 3D
        info = client.status(capture_id)
        estado = str(info.status).upper()
        
        if "FINISHED" in estado:
            model_url = ""
            # A Luma retorna os modelos processados na propriedade 'artifacts'
            if hasattr(info, 'artifacts'):
                for artifact in info.artifacts:
                    url = artifact.get('url', '')
                    # Busca o link de download do modelo em OBJ ou arquivo compactado ZIP
                    if '.obj' in url.lower() or '.zip' in url.lower():
                        model_url = url
                        break
                        
            return jsonify({'status': 'completed', 'model_url': model_url})
            
        elif "FAILED" in estado:
            return jsonify({'status': 'failed'})
            
        return jsonify({'status': estado.replace('RUNSTATUS.', '')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
