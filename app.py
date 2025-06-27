import json
import os
from flask import Flask, request, render_template, flash, redirect, url_for

# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
# Chave secreta é necessária para usar as mensagens "flash" do Flask para notificações.
# Em produção real, essa chave deveria vir de uma variável de ambiente para segurança.
app.secret_key = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao-para-desenvolvimento')

# --- Configuração de Caminho de Arquivo para Produção ---
# Esta é a parte crucial para o Render.
# Ele busca uma variável de ambiente chamada 'DATA_DIR'.
# No Render, você a definirá como '/data' (o caminho do seu Disco Persistente).
# Se a variável não for encontrada, ele usa '.' (o diretório atual),
# o que permite que o app funcione perfeitamente no seu computador local.
DATA_DIR = os.environ.get('DATA_DIR', '.')
MASTER_TOKEN_FILE = os.path.join(DATA_DIR, 'tokens.json')


def validate_and_append_tokens(uploaded_tokens):
    """
    Carrega os tokens mestre, valida os novos tokens enviados e os adiciona à cadeia.

    Retorna:
        int: O número de novos tokens válidos que foram adicionados.
    """
    # 1. Garante que o diretório de dados exista antes de qualquer operação de arquivo.
    #    Isso é importante na primeira execução em um ambiente novo como o Render.
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError as e:
        # Lidar com erros de permissão, se aplicável
        print(f"Erro ao criar o diretório {DATA_DIR}: {e}")
        return 0

    # 2. Carrega a blockchain existente do arquivo mestre.
    try:
        with open(MASTER_TOKEN_FILE, 'r', encoding='utf-8') as f:
            master_tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se o arquivo não existe ou está corrompido, começa uma nova cadeia.
        master_tokens = []

    # 3. Identifica quais tokens do upload são realmente novos, evitando duplicatas.
    #    Um set é usado para uma verificação de existência (O(1)) muito mais rápida.
    master_hashes = {token.get('hash') for token in master_tokens}
    new_tokens = [token for token in uploaded_tokens if token.get('hash') and token.get('hash') not in master_hashes]

    if not new_tokens:
        flash("Nenhum token novo foi encontrado no arquivo enviado. Todos já estavam registrados.", "error")
        return 0

    # 4. Ordena os novos tokens por 'index' para garantir a validação na ordem correta.
    new_tokens.sort(key=lambda x: x.get('index', 0))

    # 5. Encontra o último bloco válido na cadeia existente para começar a validação.
    if master_tokens:
        last_block_in_chain = max(master_tokens, key=lambda x: x['index'])
    else:
        last_block_in_chain = None # A cadeia está vazia.

    # 6. Valida cada novo token sequencialmente.
    valid_tokens_to_add = []
    for token in new_tokens:
        # A validação verifica se o novo bloco se conecta corretamente ao último da cadeia.
        index = token.get('index')
        prev_hash = token.get('prev_hash')

        # Caso 1: Bloco Gênesis (o primeiro de todos)
        is_genesis_block = last_block_in_chain is None and index == 1 and 'prev_hash' not in token

        # Caso 2: Bloco sequencial normal
        is_sequential_block = (
            last_block_in_chain and
            isinstance(index, int) and
            index == last_block_in_chain.get('index', 0) + 1 and
            prev_hash == last_block_in_chain.get('hash')
        )

        if is_genesis_block or is_sequential_block:
            valid_tokens_to_add.append(token)
            last_block_in_chain = token  # O bloco atual se torna o "último" para a próxima iteração.
        else:
            # Se um token quebra a sequência, a validação é interrompida.
            expected_index = last_block_in_chain.get('index', 0) + 1 if last_block_in_chain else 1
            flash(f"Validação interrompida! O token de índice {index} quebra a sequência. "
                  f"Esperado: índice {expected_index} e prev_hash '{last_block_in_chain.get('hash') if last_block_in_chain else 'N/A'}'.", "error")
            break # Para o loop, pois a cadeia está quebrada.

    # 7. Se houver tokens válidos, anexa-os e salva o arquivo mestre.
    if valid_tokens_to_add:
        master_tokens.extend(valid_tokens_to_add)
        
        # Ordena a lista final para garantir a consistência (embora já deva estar ordenada).
        master_tokens.sort(key=lambda x: x['index'])
        
        with open(MASTER_TOKEN_FILE, 'w', encoding='utf-8') as f:
            # `indent=2` para manter o JSON legível e `ensure_ascii=False` para caracteres especiais.
            json.dump(master_tokens, f, indent=2, ensure_ascii=False)
        
        return len(valid_tokens_to_add)
        
    return 0

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Bloco de segurança para o upload
        if 'file' not in request.files:
            flash('Nenhum campo de arquivo na requisição.', 'error')
            return redirect(request.url)
        
        file = request.files['file']

        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)

        if not file.filename.lower().endswith('.json'):
            flash('Arquivo inválido. Por favor, envie um arquivo .json.', 'error')
            return redirect(request.url)

        # Processamento do arquivo
        try:
            # file.stream é mais eficiente do que salvar o arquivo primeiro.
            uploaded_tokens = json.load(file.stream)
            if not isinstance(uploaded_tokens, list):
                raise ValueError("O conteúdo do JSON deve ser uma lista de objetos (tokens).")
        except (json.JSONDecodeError, ValueError) as e:
            flash(f'Erro ao processar o arquivo JSON: {e}', 'error')
            return redirect(request.url)

        # Chama a função principal de validação
        added_count = validate_and_append_tokens(uploaded_tokens)
        
        # Envia a notificação de sucesso ou falha para o usuário
        if added_count > 0:
            flash(f'{added_count} token(s) minerado(s) foi(ram) validado(s) e adicionado(s) com sucesso à blockchain!', 'success')
        else:
            # A função `validate_and_append_tokens` já deve ter usado `flash` para dar um erro mais específico.
            # Esta é uma mensagem genérica caso nenhum token tenha sido adicionado por outros motivos.
            if not any(True for _ in app.jinja_env.globals['get_flashed_messages']()):
                 flash('Nenhum token válido foi adicionado. Verifique o arquivo enviado e a sequência da blockchain.', 'error')

        return redirect(url_for('upload_file'))

    # Se a requisição for GET, apenas renderiza a página HTML.
    return render_template('index.html')

# Esta parte só é executada quando você roda `python app.py` diretamente.
# O Gunicorn não executa este bloco, ele importa o objeto `app` diretamente.
if __name__ == '__main__':
    # Roda o servidor de desenvolvimento do Flask.
    # O `host='0.0.0.0'` torna o servidor acessível na sua rede local.
    # O debug=True fornece mais informações de erro, mas NUNCA deve ser usado em produção.
    app.run(host='0.0.0.0', port=5001, debug=True)
