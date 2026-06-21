from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os
import threading

app = Flask(__name__)

PASTA_DESTINO = "Meus_Arquivos_Baixados"

# Status global monitorando progresso, falhas e mensagens
status_download = {
    "baixando": False, 
    "mensagem": "Nenhum download em andamento.", 
    "progresso": 0, 
    "falhas": []
}

# Variável de controle interna para saber qual item da fila está rodando
item_atual_indice = 1
item_atual_total = 1
item_atual_formato = "MP4"

def hook_de_progresso(d):
    """Captura o progresso e ajusta a mensagem caso seja uma playlist."""
    global status_download, item_atual_indice, item_atual_total, item_atual_formato
    
    if d['status'] == 'downloading':
        try:
            # Verifica se o yt-dlp está extraindo uma playlist interna
            info = d.get('info_dict', {})
            p_index = info.get('playlist_index')
            p_total = info.get('n_entries')
            
            if p_index and p_total:
                # Se for playlist, personaliza a mensagem exibida na tela
                status_download["mensagem"] = f"📥 Baixando item [{item_atual_indice}/{item_atual_total}] • Playlist ({p_index}/{p_total}) em {item_atual_formato}..."
            
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
    global status_download, item_atual_indice, item_atual_total, item_atual_formato
    status_download["baixando"] = True
    status_download["progresso"] = 0
    status_download["falhas"] = []
    
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)
        
    item_atual_total = len(fila)
    argumentos_extrator = {
        'youtube': ['player_client=android,web']
    }
    
    for indice, item in enumerate(fila, start=1):
        item_atual_indice = indice
        url = item['url']
        formato = item['formato']
        qualidade = item['qualidade']
        item_atual_formato = formato.upper()
        
        status_download["mensagem"] = f"📥 Baixando item [{indice}/{item_atual_total}] em formato {item_atual_formato}..."
        status_download["progresso"] = 0 
        
        # Configurações básicas comuns
        ydl_opts = {
            'outtmpl': os.path.join(PASTA_DESTINO, '%(title)s.%(ext)s'),
            'extractor_args': argumentos_extrator,
            'progress_hooks': [hook_de_progresso],
            'noplaylist': False, # PERMITE O DOWNLOAD DE PLAYLISTS COMPLETAS CASO O LINK SEJA DE UMA
        }
        
        # LÓGICA DO SELETOR DE QUALIDADE (Aproveitando o FFmpeg instalado)
        if formato == 'mp4':
            ydl_opts['merge_output_format'] = 'mp4'
            if qualidade == '1080p':
                ydl_opts['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best'
            elif qualidade == '360p':
                ydl_opts['format'] = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best'
            else: # 720p (Padrão)
                ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best'
        else: # Formato MP3 (Áudio sempre extrai a melhor qualidade disponível)
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
            status_download["falhas"].append(url)
            
    status_download["baixando"] = False
    status_download["progresso"] = 100
    
    if len(status_download["falhas"]) == 0:
        status_download["mensagem"] = "🎉 Todos os downloads foram concluídos com sucesso!"
    else:
        status_download["mensagem"] = f"⚠️ Fila concluída, mas {len(status_download['falhas'])} download(s) falhou(aram)."

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
    return jsonify(status_download)

@app.route('/arquivos', methods=['GET'])
def listar_arquivos():
    if not os.path.exists(PASTA_DESTINO):
        return jsonify([])
    arquivos = os.listdir(PASTA_DESTINO)
    arquivos = [f for f in arquivos if os.path.isfile(os.path.join(PASTA_DESTINO, f))]
    return jsonify(arquivos)

@app.route('/download/<path:nome_arquivo>', methods=['GET'])
def baixar_arquivo(nome_arquivo):
    return send_from_directory(PASTA_DESTINO, nome_arquivo, as_attachment=True)

# ==========================================
# NOVA ROTA: DELETAR DO SERVIDOR
# ==========================================
@app.route('/deletar/<path:nome_arquivo>', methods=['POST'])
def deletar_arquivo(nome_arquivo):
    """Remove o arquivo fisicamente do HD do computador."""
    caminho_completo = os.path.join(PASTA_DESTINO, nome_arquivo)
    if os.path.exists(caminho_completo):
        try:
            os.remove(caminho_completo)
            return jsonify({"status": "Arquivo apagado com sucesso!"})
        except Exception as e:
            return jsonify({"erro": f"Não foi possível apagar o arquivo: {e}"}), 500
    return jsonify({"erro": "Arquivo não encontrado."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)