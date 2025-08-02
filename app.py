from flask import Flask, render_template, request, redirect, session, flash, url_for
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega variáveis do .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'sua_chave_secreta_flask')

# Inicializa cliente Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL e SUPABASE_KEY devem estar definidos no arquivo .env")

supabase: Client = create_client(supabase_url, supabase_key)

# Rota de registro usando Supabase Auth
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome = request.form['nome']
        cpf = request.form['cpf']
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            # Cadastra usuário no Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": senha,
                "options": {
                    "data": {
                        "nome": nome,
                        "cpf": cpf
                    }
                }
            })
            
            if auth_response.user:
                # Salva dados extras na tabela profiles (incluindo email REAL)
                profile_data = {
                    "id": auth_response.user.id,
                    "nome": nome,
                    "cpf": cpf,
                    "email": email,  # Email REAL que o usuário digitou
                    "is_admin": False
                }
                
                try:
                    supabase.table('profiles').insert(profile_data).execute()
                except Exception as e:
                    print("Erro ao salvar perfil:", e)
                    # Se der erro, tenta atualizar em vez de inserir
                    try:
                        supabase.table('profiles').update(profile_data).eq('id', auth_response.user.id).execute()
                    except Exception as e2:
                        print("Erro ao atualizar perfil:", e2)
                        flash('Cadastro realizado, mas erro ao salvar dados extras.')
                        return redirect('/login')
                flash('Cadastro realizado com sucesso! Verifique seu e-mail para confirmar.')
            else:
                flash('Erro no cadastro. Tente novamente.')
                return redirect('/login')
                
        except Exception as e:
            print("Erro no cadastro:", e)
            flash('Erro no cadastro. Verifique os dados e tente novamente.')
            return redirect('/login')

    # Se for GET, redireciona para a página de login/cadastro
    return redirect('/login')

# Rota de login usando Supabase Auth
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            # Faz login no Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": senha
            })
            
            if auth_response.user:
                # Busca dados do perfil
                profile_response = supabase.table('profiles').select('*').eq('id', auth_response.user.id).execute()
                
                if profile_response.data:
                    profile = profile_response.data[0]
                    session['usuario'] = {
                        'id': auth_response.user.id,
                        'email': auth_response.user.email,
                        'nome': profile.get('nome', ''),
                        'cpf': profile.get('cpf', ''),
                        'confirmado': auth_response.user.email_confirmed_at is not None,
                        'is_admin': profile.get('is_admin', False)
                    }
                    
                    # Se for admin, vai direto para o painel admin
                    if profile.get('is_admin'):
                        return redirect('/admin')
                    else:
                        return redirect('/painel')
                else:
                    flash('Perfil não encontrado.')
                    return redirect('/login')
            else:
                flash('Email ou senha incorretos.')
                return redirect('/login')
                
        except Exception as e:
            print("Erro no login:", e)
            flash('Erro no login. Verifique os dados e tente novamente.')
            return redirect('/login')

    return render_template('login.html')

# Rota para confirmação do email
@app.route('/confirmar/<path:email>')
def confirmar(email):
    try:
        # Confirma o email no Supabase Auth
        supabase.auth.verify_otp({
            "email": email,
            "token": request.args.get('token', ''),
            "type": "email"
        })
        flash("Email confirmado! Agora faça login.")
    except Exception as e:
        print("Erro na confirmação:", e)
        flash("Erro na confirmação do email.")
    
    return redirect('/login')

# Rota do painel
@app.route('/painel', methods=['GET', 'POST'])
def painel():
    if 'usuario' not in session:
        return redirect('/login')
    
    usuario = session['usuario']
    
    if request.method == 'POST':
        # Atualiza dados do perfil
        dados = {
            'nome': request.form.get('nome', usuario['nome']),
            'cpf': request.form.get('cpf', usuario['cpf'])
        }
        
        try:
            supabase.table('profiles').update(dados).eq('id', usuario['id']).execute()
            flash('Dados atualizados com sucesso.')
            session['usuario'].update(dados)
        except Exception as e:
            print("Erro ao atualizar:", e)
            flash('Erro ao atualizar dados.')
        
        return redirect('/painel')

    # Busca dados profissionais do usuário
    try:
        profissional_response = supabase.table('profissionais').select('*').eq('id', usuario['id']).execute()
        profissional = profissional_response.data[0] if profissional_response.data else None
    except Exception as e:
        print("Erro ao buscar dados profissionais:", e)
        profissional = None

    return render_template('painel.html', usuario=usuario, profissional=profissional)

# Rota para salvar dados profissionais
@app.route('/salvar_profissional', methods=['POST'])
def salvar_profissional():
    if 'usuario' not in session:
        return redirect('/login')
    
    usuario = session['usuario']
    
    dados = {
        'id': usuario['id'],
        'profissao': request.form.get('profissao'),
        'horario_inicio': request.form.get('horario_inicio'),
        'horario_saida': request.form.get('horario_saida'),
        'salario': request.form.get('salario'),
        'status': request.form.get('status', 'ATIVO')
    }
    
    try:
        # Verifica se já existe registro
        existing = supabase.table('profissionais').select('*').eq('id', usuario['id']).execute()
        
        if existing.data:
            # Atualiza
            supabase.table('profissionais').update(dados).eq('id', usuario['id']).execute()
            flash('Dados profissionais atualizados com sucesso!')
        else:
            # Insere novo
            supabase.table('profissionais').insert(dados).execute()
            flash('Dados profissionais salvos com sucesso!')
            
    except Exception as e:
        print("Erro ao salvar dados profissionais:", e)
        flash('Erro ao salvar dados profissionais.')
    
    return redirect('/painel')

# Rota do painel administrativo
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'usuario' not in session:
        return redirect('/login')
    
    usuario = session['usuario']
    
    # Verifica se é admin
    try:
        profile_response = supabase.table('profiles').select('is_admin').eq('id', usuario['id']).execute()
        if not profile_response.data or not profile_response.data[0].get('is_admin'):
            flash('Acesso negado. Apenas administradores.')
            return redirect('/painel')
    except Exception as e:
        print("Erro ao verificar admin:", e)
        flash('Erro ao verificar permissões.')
        return redirect('/painel')
    
    # Busca todos os profissionais
    try:
        # Busca profissionais
        profissionais_response = supabase.table('profissionais').select('*').execute()
        profissionais = profissionais_response.data
        
        # Busca perfis dos usuários
        if profissionais:
            user_ids = [prof['id'] for prof in profissionais]
            profiles_response = supabase.table('profiles').select('*').in_('id', user_ids).execute()
            profiles_dict = {profile['id']: profile for profile in profiles_response.data}
            
            # Combina os dados
            for prof in profissionais:
                profile = profiles_dict.get(prof['id'], {})
                prof['profile'] = profile
        else:
            profissionais = []
    except Exception as e:
        print("Erro ao buscar profissionais:", e)
        profissionais = []
    
    return render_template('admin.html', profissionais=profissionais)

# Rota para editar profissional (admin)
@app.route('/admin/editar/<user_id>', methods=['POST'])
def editar_profissional(user_id):
    if 'usuario' not in session:
        return redirect('/login')
    
    # Verifica se é admin
    usuario = session['usuario']
    try:
        profile_response = supabase.table('profiles').select('is_admin').eq('id', usuario['id']).execute()
        if not profile_response.data or not profile_response.data[0].get('is_admin'):
            flash('Acesso negado.')
            return redirect('/admin')
    except Exception as e:
        flash('Erro ao verificar permissões.')
        return redirect('/admin')
    
    # Dados do perfil
    profile_data = {
        'nome': request.form.get('nome'),
        'email': request.form.get('email'),
        'cpf': request.form.get('cpf')
    }
    
    # Dados profissionais
    profissional_data = {
        'profissao': request.form.get('profissao'),
        'horario_inicio': request.form.get('horario_inicio'),
        'horario_saida': request.form.get('horario_saida'),
        'salario': request.form.get('salario'),
        'status': request.form.get('status', 'ATIVO')
    }
    
    try:
        # Atualiza dados do perfil
        supabase.table('profiles').update(profile_data).eq('id', user_id).execute()
        
        # Atualiza dados profissionais
        supabase.table('profissionais').update(profissional_data).eq('id', user_id).execute()
        
        flash('Profissional atualizado com sucesso!')
    except Exception as e:
        print("Erro ao atualizar profissional:", e)
        flash('Erro ao atualizar profissional.')
    
    return redirect('/admin')

# Rota para excluir profissional (admin)
@app.route('/admin/excluir/<user_id>', methods=['POST'])
def excluir_profissional(user_id):
    if 'usuario' not in session:
        return redirect('/login')
    
    # Verifica se é admin
    usuario = session['usuario']
    try:
        profile_response = supabase.table('profiles').select('is_admin').eq('id', usuario['id']).execute()
        if not profile_response.data or not profile_response.data[0].get('is_admin'):
            flash('Acesso negado.')
            return redirect('/admin')
    except Exception as e:
        flash('Erro ao verificar permissões.')
        return redirect('/admin')
    
    try:
        supabase.table('profissionais').delete().eq('id', user_id).execute()
        flash('Profissional excluído com sucesso!')
    except Exception as e:
        print("Erro ao excluir profissional:", e)
        flash('Erro ao excluir profissional.')
    
    return redirect('/admin')

# Rota de login administrativo
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            # Faz login no Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": senha
            })
            
            if auth_response.user:
                # Verifica se é admin
                profile_response = supabase.table('profiles').select('*').eq('id', auth_response.user.id).execute()
                
                if profile_response.data and profile_response.data[0].get('is_admin'):
                    profile = profile_response.data[0]
                    session['usuario'] = {
                        'id': auth_response.user.id,
                        'email': auth_response.user.email,
                        'nome': profile.get('nome', ''),
                        'cpf': profile.get('cpf', ''),
                        'confirmado': auth_response.user.email_confirmed_at is not None,
                        'is_admin': True
                    }
                    return redirect('/admin')
                else:
                    flash('Acesso negado. Apenas administradores podem acessar este painel.')
                    return redirect('/admin/login')
            else:
                flash('Email ou senha incorretos.')
                return redirect('/admin/login')
                
        except Exception as e:
            print("Erro no login admin:", e)
            flash('Erro no login. Verifique os dados e tente novamente.')
            return redirect('/admin/login')

    return render_template('admin_login.html')



# Logout
@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    session.clear()
    return redirect('/login')

# Rota de teste para autocomplete
@app.route('/teste_autocomplete')
def teste_autocomplete():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste Autocomplete</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 40px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: white;
            }
            .container {
                max-width: 500px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                padding: 30px;
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .form-group { 
                margin: 20px 0; 
            }
            label {
                display: block;
                margin-bottom: 5px;
                color: white;
                font-weight: bold;
            }
            input { 
                padding: 12px; 
                width: 100%;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.9);
                color: #333;
                font-size: 16px;
                box-sizing: border-box;
            }
            input:focus {
                outline: none;
                background: white;
                border-color: #673F85;
                box-shadow: 0 0 10px rgba(103, 63, 133, 0.3);
            }
            button { 
                padding: 12px 24px; 
                background: #673F85; 
                color: white; 
                border: none; 
                border-radius: 8px; 
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
                margin-top: 10px;
            }
            button:hover {
                background: #8B5A96;
                transform: translateY(-2px);
            }
            .info { 
                background: rgba(255, 255, 255, 0.1); 
                padding: 20px; 
                border-radius: 10px; 
                margin: 20px 0;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .status {
                background: rgba(0, 255, 0, 0.2);
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                border: 1px solid rgba(0, 255, 0, 0.3);
            }
            .warning {
                background: rgba(255, 165, 0, 0.2);
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                border: 1px solid rgba(255, 165, 0, 0.3);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 Teste de Autocomplete</h1>
            
            <div class="info">
                <h3>📋 Como testar:</h3>
                <ol>
                    <li>Digite um e-mail e senha nos campos abaixo</li>
                    <li>Clique em "Testar Formulário"</li>
                    <li>Recarregue a página (F5)</li>
                    <li>Clique no campo de e-mail - deve aparecer o e-mail que você digitou</li>
                    <li>Teste também o campo de senha</li>
                </ol>
            </div>
            
            <form autocomplete="on" method="POST" action="/teste_autocomplete">
                <div class="form-group">
                    <label>Email:</label>
                    <input type="email" name="email" placeholder="Digite um email" autocomplete="username" required>
                </div>
                
                <div class="form-group">
                    <label>Senha:</label>
                    <input type="password" name="senha" placeholder="Digite uma senha" autocomplete="current-password" required>
                </div>
                
                <button type="submit">Testar Formulário</button>
            </form>
            
            <div class="info">
                <h3>✅ Status do Autocomplete:</h3>
                <div class="status">✅ Formulário configurado com autocomplete="on"</div>
                <div class="status">✅ Campo email com autocomplete="username"</div>
                <div class="status">✅ Campo senha com autocomplete="current-password"</div>
                <div class="status">✅ Estilos CSS otimizados para autocomplete</div>
                <div class="warning">⚠️ <strong>Importante:</strong> O navegador só salva os dados após você submeter o formulário</div>
                <div class="warning">⚠️ <strong>Dica:</strong> Alguns navegadores podem pedir permissão para salvar senhas</div>
            </div>
            
            <div class="info">
                <h3>🔧 Solução de Problemas:</h3>
                <ul>
                    <li>Se não funcionar, verifique se o navegador permite salvar senhas</li>
                    <li>Teste em modo incógnito/privado</li>
                    <li>Verifique se não há extensões bloqueando o autocomplete</li>
                    <li>Certifique-se de que o formulário foi submetido pelo menos uma vez</li>
                </ul>
            </div>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="/login" style="color: #FFD700; text-decoration: none; font-weight: bold;">← Voltar ao Login</a>
            </p>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True) 