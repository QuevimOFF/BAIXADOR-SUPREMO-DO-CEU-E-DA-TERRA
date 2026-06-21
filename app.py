from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os
import threading

app = Flask(__name__)

PASTA_DESTINO = "Meus_Arquivos_Baixados"

# Dicionário global para monitorar o status do download em tempo real
status_download = {"baixando": False, "mensagem": "Nenhum download em andamento.", "progresso": 0}

def hook_de_progresso(d):
    """Função que captura o progresso em tempo real do yt-dlp."""
    global status_download
    if d['status'] == 'downloading':
        try:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                baixado = d.get('downloaded_bytes', 0)
                porcentagem = (baixado / total_bytes) * 100
                status_download["progresso"] = round(porcentagem, 1)
        except:
            pass
    elif d['status'] == 'finished':
        status_download["progresso"] = 100

def executar_fila_downloads(fila):
    """Executa os downloads em segundo plano (Thread)."""
    global status_download
    status_download["baixando"] = True
    status_download["progresso"] = 0
    
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)
        
    total_itens = len(fila)
    argumentos_extrator = {
        'youtube': ['player_client=android,web']
    }
    
    for indice, item in enumerate(fila, start=1):
        url = item['url']
        formato = item['formato']
        
        status_download["mensagem"] = f"📥 Baixando item [{indice}/{total_itens}] em formato {formato.upper()}..."
        status_download["progresso"] = 0 
        
        ydl_opts = {
            'outtmpl': os.path.join(PASTA_DESTINO, '%(title)s.%(ext)s'),
            'extractor_args': argumentos_extrator,
            'progress_hooks': [hook_de_progresso],
        }
        
        if formato == 'mp4':
            ydl_opts['format'] = 'best'
        else: # Formato MP3
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"Erro ao baixar {url}: {e}")
            
    # Finaliza a fila
    status_download["baixando"] = False
    status_download["progresso"] = 100
    status_download["mensagem"] = "🎉 Todos os downloads da fila foram concluídos com sucesso!"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/iniciar', methods=['POST'])
def iniciar_download():
    global status_download
    if status_download["baixando"]:
        return jsonify({"erro": "Já existe um download em andamento no servidor!"}), 400
        
    dados = request.get_json()
    fila = dados.get('fila', [])
    
    if not fila:
        return jsonify({"erro": "A fila enviada está vazia."}), 400
        
    thread = threading.Thread(target=executar_fila_downloads, args=(fila,))
    thread.start()
    
    return jsonify({"status": "Processamento iniciado!"})

@app.route('/status', methods=['GET'])
def obter_status():
    global status_download
    return jsonify(status_download)

# ==========================================
# NOVAS ROTAS: MEUS ARQUIVOS
# ==========================================
@app.route('/arquivos', methods=['GET'])
def listar_arquivos():
    """Lê a pasta do servidor e devolve a lista de arquivos prontos."""
    if not os.path.exists(PASTA_DESTINO):
        return jsonify([])
        
    arquivos = os.listdir(PASTA_DESTINO)
    # Garante que só vai listar arquivos de verdade (ignora pastas acidentais)
    arquivos = [f for f in arquivos if os.path.isfile(os.path.join(PASTA_DESTINO, f))]
    return jsonify(arquivos)

@app.route('/download/<path:nome_arquivo>', methods=['GET'])
def baixar_arquivo(nome_arquivo):
    """Pega o arquivo do computador e envia pela rede para o dispositivo do usuário (Celular/PC)."""
    return send_from_directory(PASTA_DESTINO, nome_arquivo, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)