# app.py CORRIGIDO

import json
import os
from flask import Flask, request, render_template, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao-para-desenvolvimento')

DATA_DIR = os.environ.get('DATA_DIR', '.')
MASTER_TOKEN_FILE = os.path.join(DATA_DIR, 'tokens.json')


def validate_and_append_tokens(uploaded_tokens):
    """
    Carrega os tokens mestre, valida os novos tokens enviados e os adiciona à cadeia.
    """
    # A verificação e criação do diretório foi REMOVIDA daqui.
    # Assumimos que o diretório /data já existe no Render.

    try:
        with open(MASTER_TOKEN_FILE, 'r', encoding='utf-8') as f:
            master_tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        master_tokens = []

    master_hashes = {token.get('hash') for token in master_tokens}
    new_tokens = [token for token in uploaded_tokens if token.get('hash') and token.get('hash') not in master_hashes]

    if not new_tokens:
        flash("Nenhum token novo foi encontrado no arquivo enviado. Todos já estavam registrados.", "error")
        return 0

    new_tokens.sort(key=lambda x: x.get('index', 0))

    if master_tokens:
        last_block_in_chain = max(master_tokens, key=lambda x: x['index'])
    else:
        last_block_in_chain = None

    valid_tokens_to_add = []
    for token in new_tokens:
        index = token.get('index')
        prev_hash = token.get('prev_hash')
        is_genesis_block = last_block_in_chain is None and index == 1 and 'prev_hash' not in token
        is_sequential_block = (
            last_block_in_chain and
            isinstance(index, int) and
            index == last_block_in_chain.get('index', 0) + 1 and
            prev_hash == last_block_in_chain.get('hash')
        )

        if is_genesis_block or is_sequential_block:
            valid_tokens_to_add.append(token)
            last_block_in_chain = token
        else:
            expected_index = last_block_in_chain.get('index', 0) + 1 if last_block_in_chain else 1
            flash(f"Validação interrompida! O token de índice {index} quebra a sequência. "
                  f"Esperado: índice {expected_index} e prev_hash '{last_block_in_chain.get('hash') if last_block_in_chain else 'N/A'}'.", "error")
            break

    if valid_tokens_to_add:
        master_tokens.extend(valid_tokens_to_add)
        master_tokens.sort(key=lambda x: x['index'])
        
        with open(MASTER_TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_tokens, f, indent=2, ensure_ascii=False)
        
        return len(valid_tokens_to_add)
        
    return 0

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
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

        try:
            uploaded_tokens = json.load(file.stream)
            if not isinstance(uploaded_tokens, list):
                raise ValueError("O conteúdo do JSON deve ser uma lista de objetos (tokens).")
        except (json.JSONDecodeError, ValueError) as e:
            flash(f'Erro ao processar o arquivo JSON: {e}', 'error')
            return redirect(request.url)

        added_count = validate_and_append_tokens(uploaded_tokens)
        
        if added_count > 0:
            flash(f'{added_count} token(s) minerado(s) foi(ram) validado(s) e adicionado(s) com sucesso à blockchain!', 'success')
        else:
            if not any(True for _ in app.jinja_env.globals['get_flashed_messages']()):
                 flash('Nenhum token válido foi adicionado. Verifique o arquivo enviado e a sequência da blockchain.', 'error')

        return redirect(url_for('upload_file'))

    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
