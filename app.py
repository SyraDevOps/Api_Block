# app.py
import json
import os
from flask import Flask, request, render_template, flash, redirect, url_for

# Inicializa a aplicação Flask
app = Flask(__name__)
# Chave secreta necessária para usar o sistema de mensagens 'flash'
app.secret_key = 'syra_validator_secret_key'

# Constante para o nome do arquivo da blockchain principal
MASTER_TOKEN_FILE = 'tokens.json'

def validate_and_append_tokens(uploaded_tokens):
    """
    Função principal que valida novos tokens e os adiciona ao arquivo mestre.
    """
    # 1. Carrega os tokens existentes do arquivo mestre
    try:
        with open(MASTER_TOKEN_FILE, 'r', encoding='utf-8') as f:
            master_tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se o arquivo não existir ou estiver vazio/corrompido, começa com uma lista vazia
        master_tokens = []

    # 2. Identifica quais tokens do upload são realmente novos
    master_hashes = {token['hash'] for token in master_tokens}
    new_tokens = [token for token in uploaded_tokens if token.get('hash') not in master_hashes]

    if not new_tokens:
        flash("Nenhum token novo foi encontrado no arquivo enviado.", "error")
        return 0

    # 3. Ordena os novos tokens pelo 'index' para validar em sequência
    new_tokens.sort(key=lambda x: x.get('index', 0))

    # 4. Encontra o último bloco válido na cadeia existente
    if master_tokens:
        last_block_in_chain = max(master_tokens, key=lambda x: x['index'])
    else:
        last_block_in_chain = None

    # 5. Valida cada novo token em sequência
    valid_tokens_to_add = []
    for token in new_tokens:
        # A validação garante que o novo bloco se conecta corretamente ao último bloco da cadeia
        is_genesis_block = last_block_in_chain is None and token.get('index') == 1
        
        is_sequential_block = (
            last_block_in_chain and
            token.get('index') == last_block_in_chain.get('index', 0) + 1 and
            token.get('prev_hash') == last_block_in_chain.get('hash')
        )

        if is_genesis_block or is_sequential_block:
            valid_tokens_to_add.append(token)
            last_block_in_chain = token  # Atualiza o 'último bloco' para o bloco atual
        else:
            # Se um token quebra a sequência, paramos de adicionar
            flash(f"Validação interrompida. O token de índice {token.get('index')} quebra a sequência da blockchain.", "error")
            break

    # 6. Se houver tokens válidos, adiciona-os e salva o arquivo mestre
    if valid_tokens_to_add:
        master_tokens.extend(valid_tokens_to_add)
        
        # Garante que a lista final esteja ordenada
        master_tokens.sort(key=lambda x: x['index'])
        
        with open(MASTER_TOKEN_FILE, 'w', encoding='utf-8') as f:
            # indent=2 para manter o JSON legível
            json.dump(master_tokens, f, indent=2, ensure_ascii=False)
        
        return len(valid_tokens_to_add)
        
    return 0

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Verifica se um arquivo foi enviado na requisição
        if 'file' not in request.files:
            flash('Nenhum arquivo foi enviado.', 'error')
            return redirect(request.url)
        
        file = request.files['file']

        # Verifica se o nome do arquivo está vazio (usuário não selecionou nada)
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)

        # Processa o arquivo se ele existir e for um JSON
        if file and file.filename.endswith('.json'):
            try:
                # Carrega o conteúdo do arquivo JSON enviado
                uploaded_tokens = json.load(file.stream)
                if not isinstance(uploaded_tokens, list):
                    raise ValueError("O JSON deve ser uma lista de tokens.")
            except (json.JSONDecodeError, ValueError) as e:
                flash(f'Erro ao ler o arquivo JSON: {e}', 'error')
                return redirect(request.url)

            # Chama a função de validação e obtém o número de tokens adicionados
            added_count = validate_and_append_tokens(uploaded_tokens)
            
            if added_count > 0:
                flash(f'{added_count} token(s) minerado(s) foi(ram) validado(s) e adicionado(s) à blockchain!', 'success')
            else:
                flash('Nenhum token válido foi adicionado. Verifique os logs ou o arquivo enviado.', 'error')
            
            return redirect(url_for('upload_file'))

    # Se a requisição for GET, apenas exibe a página de upload
    return render_template('index.html')

if __name__ == '__main__':
    # Roda a aplicação em modo de debug
    app.run(debug=True, port=5001)
