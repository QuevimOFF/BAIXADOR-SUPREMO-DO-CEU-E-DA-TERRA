from flask import Flask, render_template, request, jsonify
import yt_dlp
import os
import threading

app = Flask(__name__)

PASTA_DESTINO = "Meus_Arquivos_Baixados"

# Variável global para monitorar o andamento dos downloads no site
status_download = {"baixando": False, "mensagem": "Nenhum download em andamento."}

def executar_fila_downloads(fila):
    """Função executada em segundo plano para baixar a fila sem travar o site."""
    global status_download
    status_download["baixando"] = True
    
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)
        
    total_itens = len(fila)
    argumentos_extrator = {
        'youtube': ['player_client=android,web']
    }
    
    for indice, item in enumerate(fila, start=1):
        url = item['url']
        formato = item['formato']
        
        # Atualiza a mensagem que o usuário verá na tela do site
        status_download["mensagem"] = f"📥 Baixando item [{indice}/{total_itens}] em formato {formato.upper()}..."
        
        if formato == 'mp4':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(PASTA_DESTINO, '%(title)s.%(ext)s'),
                'extractor_args': argumentos_extrator,
            }
        else: # mp3
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(PASTA_DESTINO, '%(title)s.%(ext)s'),
                'extractor_args': argumentos_extrator,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"Erro ao baixar {url}: {e}")
            
    # Finaliza o processo
    status_download["baixando"] = False
    status_download["mensagem"] = "🎉 Todos os downloads da fila foram concluídos com sucesso!"

@app.route('/')
def home():
    """Rota que carrega a página inicial do site."""
    return render_template('index.html')

@app.route('/iniciar', methods=['POST'])
def iniciar_download():
    """Rota que recebe a fila do site e inicia o processo."""
    global status_download
    if status_download["baixando"]:
        return jsonify({"erro": "Já existe um download em andamento no servidor!"}), 400
        
    dados = request.get_json()
    fila = dados.get('fila', [])
    
    if not fila:
        return jsonify({"erro": "A fila enviada está vazia."}), 400
        
    # Dispara a thread em segundo plano para o site continuar respondendo livremente
    thread = threading.Thread(target=executar_fila_downloads, args=(fila,))
    thread.start()
    
    return jsonify({"status": "Processamento iniciado!"})

@app.route('/status', methods=['GET'])
def obter_status():
    """Rota consultada automaticamente pelo JavaScript para atualizar a tela."""
    global status_download
    return jsonify(status_download)

if __name__ == '__main__':
    # O host='0.0.0.0' é o segredo para permitir o acesso de outros aparelhos da casa
    app.run(host='0.0.0.0', port=5000, debug=True)