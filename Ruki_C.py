# -*- coding: UTF-8 -*-
"""
Ruki-C v1.4 - Robot Universal Kit (Compiler)
Interface PyWebView + HTML/CSS/SVG
"""

import sys, os, json, gzip, re, math, traceback
import xml.etree.ElementTree as ET
import importlib.util

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==============================================================================

RUKI_VERSION = "1.4"

# Diretório base do programa (compatível com PyInstaller onefile/onedir)
if getattr(sys, "frozen", False):
    # onefile: arquivos extraídos em sys._MEIPASS
    # onedir: cai para a pasta do executável
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Caminhos dos assets
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
# fallback extra: se estiver frozen e assets não estiverem em BASE_DIR, tenta ao lado do .exe
if getattr(sys, "frozen", False) and not os.path.isdir(ASSETS_DIR):
    alt = os.path.join(os.path.dirname(sys.executable), "assets")
    if os.path.isdir(alt):
        ASSETS_DIR = alt
ROBOTS_DIR = os.path.join(ASSETS_DIR, 'robots')
ICON_PATH = os.path.join(ASSETS_DIR, 'app.ico')
EMITTERS_DIR = os.path.join(ASSETS_DIR, 'emitters')

# Debug - mostra no CMD
print(f"=" * 50)
print(f"Ruki-C v{RUKI_VERSION}")
print(f"=" * 50)
print(f"Base: {BASE_DIR}")
print(f"Assets: {ASSETS_DIR}")
print(f"Robots: {ROBOTS_DIR}")
print(f"Ícone: {ICON_PATH}")

# Verifica se pastas existem
if not os.path.exists(ASSETS_DIR):
    print(f"ERRO: Pasta assets/ não encontrada!")
    print(f"Esperado em: {ASSETS_DIR}")
if not os.path.exists(ROBOTS_DIR):
    print(f"ERRO: Pasta assets/robots/ não encontrada!")
    print(f"Esperado em: {ROBOTS_DIR}")
else:
    arquivos = os.listdir(ROBOTS_DIR)
    print(f"Arquivos em robots/: {arquivos}")

print(f"=" * 50)

# ==============================================================================
# CARREGAMENTO DE DADOS
# ==============================================================================

def carregar_dados_robos():
    """Carrega dados dos robôs dos arquivos JSON"""
    marcas = {}
    
    if not os.path.exists(ROBOTS_DIR):
        print(f"AVISO: Pasta não existe: {ROBOTS_DIR}")
        return marcas
    
    for arq in os.listdir(ROBOTS_DIR):
        if arq.endswith('.json'):
            caminho = os.path.join(ROBOTS_DIR, arq)
            print(f"Carregando: {caminho}")
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                marca = dados.get('marca', arq.replace('.json', ''))
                marcas[marca] = {
                    'modelo_padrao': dados.get('modelo_padrao', ''),
                    'modelos_ordem': dados.get('modelos_ordem', []),
                    'robos': dados.get('robos', {})
                }
                print(f"  ✓ {marca}: {len(dados.get('robos', {}))} modelos")
            except Exception as e:
                print(f"  ✗ Erro ao carregar {arq}: {e}")
                traceback.print_exc()
    
    return marcas

def carregar_emitter(marca):
    """Carrega emitter de assets/emitters/ (igual v1.1)"""
    nome_arquivo = marca.lower().replace(' ', '_') + '.py'
    caminho = os.path.join(EMITTERS_DIR, nome_arquivo)
    if not os.path.exists(caminho):
        return None
    try:
        spec = importlib.util.spec_from_file_location(f"emitter_{marca}", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    except Exception as e:
        print(f"  ✗ Erro ao carregar emitter {marca}: {e}")
        traceback.print_exc()
        return None

def executar_conversao(marca, conv, arquivo, modelo, pasta):
    if marca not in EMITTERS:
        return False, f"Emitter não encontrado para {marca}", None
    em = EMITTERS[marca]
    if not hasattr(em, 'CONVERSOES') or conv not in em.CONVERSOES:
        return False, f"Conversão '{conv}' não disponível", None
    info = em.CONVERSOES[conv]
    robot_data = get_robot_data(marca, modelo)
    try:
        return info['conversor'](arquivo, robot_data, pasta)
    except Exception as e:
        traceback.print_exc()
        return False, f"Erro: {str(e)}", None


# Carrega dados no início
DADOS_ROBOS = carregar_dados_robos()

EMITTERS = {}
for marca in list(DADOS_ROBOS.keys()):
    em = carregar_emitter(marca)
    if em and hasattr(em, 'CONVERSOES'):
        EMITTERS[marca] = em
        print(f"  ✓ Emitter: {marca} ({len(em.CONVERSOES)} conversões)")
    else:
        # se você quer “igual v1.1”, não mostra marca sem emitter
        DADOS_ROBOS.pop(marca, None)


if not DADOS_ROBOS:
    print("\n" + "!" * 50)
    print("ATENÇÃO: Nenhum dado de robô foi carregado!")
    print("Verifique se existe o arquivo:")
    print(f"  {ROBOTS_DIR}/universal_robots.json")
    print("!" * 50 + "\n")

# ==============================================================================
# HTML/CSS INTERFACE
# ==============================================================================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Ruki-C v1.4</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#fff;--text:#000;--text2:#a5a5a5;--border:#000;--input-bg:#fff;--green:#25d66c;--subtitle:#003319}
[data-theme="dark"]{--bg:#323232;--text:#fff;--text2:#727272;--border:#fff;--input-bg:#323232;--subtitle:#fff}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:20px;transition:all .3s}
.header{display:flex;flex-direction:column;align-items:center;margin-bottom:25px;position:relative}
.logo-row{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.logo-icon{width:48px;height:48px}
.logo-text{height:35px}
.subtitle{font-size:9px;font-weight:500;color:var(--subtitle);text-align:center}
.theme-toggle{position:absolute;top:0;right:0;width:36px;height:36px;border-radius:6px;border:1px solid var(--border);cursor:pointer;background:var(--bg);display:flex;align-items:center;justify-content:center}
.theme-toggle:hover{opacity:.8}
.theme-toggle svg{width:18px;height:18px;fill:var(--text)}
.form-container{max-width:400px;margin:0 auto}
.form-group{margin-bottom:18px}
.form-label{display:block;font-size:11.5px;font-weight:500;margin-bottom:5px}
.form-hint{font-size:11.5px;color:var(--text2);margin-top:3px}
.form-select,.form-input{width:100%;height:30px;padding:0 10px;font-size:11.5px;font-family:'Segoe UI',sans-serif;border:.5px solid var(--border);border-radius:3px;background:var(--input-bg);color:var(--text);appearance:none;cursor:pointer}
.form-select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath fill='%23666' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;background-size:8px;padding-right:28px}
[data-theme="dark"] .form-select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath fill='%23fff' d='M6 8L0 0h12z'/%3E%3C/svg%3E")}
.input-group{display:flex;gap:8px}
.input-group .form-input{flex:1}
.btn-secondary{height:30px;padding:0 14px;font-size:11.5px;font-family:'Segoe UI',sans-serif;border:.5px solid var(--border);border-radius:5px;background:var(--input-bg);color:var(--text);cursor:pointer;white-space:nowrap}
.btn-secondary:hover{opacity:.7}
.btn-converter{display:flex;align-items:center;justify-content:center;gap:8px;width:120px;height:32px;margin:25px auto 0;font-size:11.5px;font-weight:500;font-family:'Segoe UI',sans-serif;color:#fff;background:var(--green);border:none;border-radius:3px;cursor:pointer}
.btn-converter:hover{filter:brightness(1.1);transform:translateY(-1px)}
.btn-converter svg{width:12px;height:12px}
.footer{position:fixed;bottom:15px;left:0;right:0;text-align:center;font-size:11.5px;color:var(--text2)}
.footer a{color:var(--text2);text-decoration:none}
.status{margin-top:18px;padding:10px;border-radius:4px;font-size:11.5px;display:none;white-space:pre-wrap}
.status.success{display:block;background:rgba(37,214,108,.12);border:1px solid var(--green);color:var(--green)}
.status.error{display:block;background:rgba(214,37,37,.12);border:1px solid #d62525;color:#d62525}
.detected-badge{display:inline-block;padding:2px 6px;font-size:9px;border-radius:3px;background:rgba(37,214,108,.15);color:var(--green);margin-left:6px}
</style>
</head>
<body>
<div class="header">
<button class="theme-toggle" onclick="toggleTheme()" title="Alternar tema">
<svg class="sun-icon" viewBox="0 0 24 24" fill="white" stroke="white" style="display:none"><circle cx="12" cy="12" r="5"/><g stroke="white" stroke-width="2"><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></g></svg>
<svg class="moon-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
</button>
<div class="logo-row">
<svg class="logo-icon" viewBox="0 0 48.48 48.48"><rect fill="#25d66c" width="48.48" height="48.48" rx="6.01"/><path fill="#fff" d="M19.32,31.85h-1.5c-.79,0-1.43-.64-1.43-1.43v-12.38c0-.79.64-1.43,1.43-1.43h1.5c.4,0,.72.32.72.72s-.32.72-.72.72h-1.49v12.36h1.49c.4,0,.72.32.72.72s-.32.72-.72.72ZM31.62,30.42v-12.38c0-.79-.64-1.43-1.43-1.43h-1.5c-.4,0-.72.32-.72.72s.32.72.72.72h1.49v12.36h-1.49c-.4,0-.72.32-.72.72s.32.72.72.72h1.5c.79,0,1.43-.64,1.43-1.43ZM39.61,36.6c0,1.79-1.45,3.24-3.24,3.24-1.5,0-2.75-1.01-3.12-2.39h-18.49c-.37,1.38-1.62,2.39-3.12,2.39-1.79,0-3.24-1.45-3.24-3.24,0-1.49,1.01-2.75,2.38-3.12l-.28-1.03-2.25-8.22,2.25-8.22.28-1.03c-1.38-.38-2.38-1.63-2.38-3.12,0-1.79,1.45-3.24,3.24-3.24,1.49,0,2.75,1.01,3.12,2.39h18.49c.37-1.38,1.62-2.39,3.12-2.39,1.79,0,3.24,1.45,3.24,3.24,0,1.49-1.01,2.75-2.38,3.12l.28,1.03,2.25,8.22-2.25,8.22-.28,1.03c1.37.38,2.38,1.63,2.38,3.12ZM35.52,16.09c-.1-.02-.19-.04-.29-.07-1.46-.39-2.61-1.55-3.01-3.01l-8.22,2.25-8.21-2.25c-.4,1.46-1.55,2.61-3.01,3.01-.1.03-.19.05-.29.07v16.3c.1.02.19.04.29.07,1.46.4,2.61,1.55,3.01,3.01l8.21-2.25,8.22,2.25c.39-1.46,1.55-2.61,3.01-3.01.1-.03.19-.05.29-.07v-16.3Z"/></svg>
<svg class="logo-text" viewBox="0 0 106 35"><path fill="#25d66c" d="M16.92,21.47c4.55,0,4.55-4.55,4.55-9.1s0-9.04-9.1-9.1H1v31.84s4.55,0,4.55,0v-13.65s6.7,0,6.82,0l6.82,13.65h4.59l-6.87-13.65ZM10.1,16.92h-4.55v-9.1h4.55c4.55,0,6.82,0,6.82,4.55s-2.27,4.55-6.82,4.55Z"/><path fill="#25d66c" d="M50.65,30.54v4.55h-7.96s0,.02-2.27.02-2.28,0-4.55,0c-4.55,0-6.82-4.55-6.82-9.08v-15.53h4.55v15.53c0,2.25,0,4.53,4.55,4.53s4.55-2.27,4.55-4.57v-15.9h4.55v20.45h3.41Z"/><path fill="#25d66c" d="M78.42,35.11h-5.96l-4.96-9.53c-1.07.25-2.85.38-4.09.38l-2.73.05v9.1h-4.55V1h4.55v20.47c2.27,0,4.55,0,6.53-.85,1.34-.58,2.3-1.82,3.03-3.38s1.46-4.55,1.81-7.14h4.55c-.64,5.02-1.79,9.68-4.01,12.16-.4.44-.82.84-1.26,1.2l7.09,11.66Z"/><polygon fill="#25d66c" points="106.08 30.56 106.08 35.11 83.34 35.11 83.34 30.56 92.44 30.56 92.44 14.64 85.61 14.64 85.61 10.09 97 10.09 97 30.56 106.08 30.56"/><rect fill="#25d66c" x="92.44" y="0" width="4.55" height="4.55"/></svg>
</div>
<div class="subtitle">Portabilidade cinemática entre controladores robóticos</div>
</div>
<div class="form-container">
<div class="form-group"><label class="form-label">Marca:</label><select class="form-select" id="marca" onchange="onMarcaChange()"></select></div>
<div class="form-group"><label class="form-label">Conversão:</label><select class="form-select" id="conversao" onchange="onConversaoChange()"></select><div class="form-hint" id="conversao-hint"></div></div>
<div class="form-group"><label class="form-label">Arquivo:</label><div class="input-group"><input type="text" class="form-input" id="arquivo" readonly placeholder="Nenhum arquivo selecionado"><button class="btn-secondary" onclick="selecionarArquivo()">Selecionar...</button></div></div>
<div class="form-group"><label class="form-label">Modelo:<span class="detected-badge" id="detected-badge" style="display:none">Detectado</span></label><select class="form-select" id="modelo"></select><div class="form-hint" id="modelo-hint"></div></div>
<div class="form-group"><label class="form-label">Pasta destino:</label><div class="input-group"><input type="text" class="form-input" id="pasta" readonly placeholder="Mesma pasta do arquivo"><button class="btn-secondary" onclick="selecionarPasta()">Selecionar...</button></div></div>
<button class="btn-converter" onclick="converter()"><svg viewBox="0 0 14 14" fill="white"><path d="M3,6l-2.5,3c-.08.1-.02.25.12.25h1.4c.08,0,.15.07.15.15v3.2c0,.14.17.21.27.1l3.1-3.3c.08-.08.03-.18-.07-.18h-1.25c-.08,0-.15-.07-.15-.15v-3.9c0-.14-.18-.21-.27-.1Z"/><path d="M11,8l2.5-3c.08-.1.02-.25-.12-.25h-1.4c-.08,0-.15-.07-.15-.15v-3.2c0-.14-.17-.21-.27-.1l-3.1,3.3c-.08.08-.03.18.07.18h1.25c.08,0,.15.07.15.15v3.9c0,.14.18.21.27.1Z"/></svg>CONVERTER</button>
<div class="status" id="status"></div>
</div>
<div class="footer">Ruki v1.4 • <a href="#" onclick="openLink('https://github.com/Borbofruto/Ruki')">github.com/Borbofruto/Ruki</a></div>
<script>
let dadosRobos={},conversoes={};
async function boot(){
  try{
    const dados = await pywebview.api.get_dados();
    dadosRobos = dados.robos || {};
    conversoes = dados.conversoes || {};

    const marcaSelect = document.getElementById('marca');
    marcaSelect.innerHTML = '';

    const marcas = Object.keys(dadosRobos);
    if(marcas.length===0){
      showStatus('Nenhum robô carregado. Verifique a pasta assets/robots/','error');
      return;
    }

    for(const marca of marcas){
      const opt=document.createElement('option');
      opt.value=marca; opt.textContent=marca;
      marcaSelect.appendChild(opt);
    }

    onMarcaChange();
    let theme='dark';
    try{ theme = localStorage.getItem('ruki-theme') || 'dark'; }catch(e){ theme='dark'; }
    setTheme(theme);

  }catch(e){
    showStatus('Erro ao carregar dados: '+e,'error');
  }
}

// robusto: se já estiver pronto, roda; se não, espera o evento
if (window.pywebview && window.pywebview.api) {
  boot();
} else {
  window.addEventListener('pywebviewready', boot);
}
function onMarcaChange(){
const marca=document.getElementById('marca').value;
if(!marca||!conversoes[marca])return;
const convSelect=document.getElementById('conversao');
convSelect.innerHTML='';
for(const conv of Object.keys(conversoes[marca])){
const opt=document.createElement('option');
opt.value=conv;opt.textContent=conv;
convSelect.appendChild(opt);
}
const dados=dadosRobos[marca];
const modeloSelect=document.getElementById('modelo');
modeloSelect.innerHTML='';
for(const modelo of dados.modelos_ordem){
const opt=document.createElement('option');
opt.value=modelo;opt.textContent=modelo;
opt.disabled=modelo.startsWith('──');
if(modelo===dados.modelo_padrao)opt.selected=true;
modeloSelect.appendChild(opt);
}
onConversaoChange();
}
function onConversaoChange(){
const marca=document.getElementById('marca').value;
const conv=document.getElementById('conversao').value;
if(marca&&conv&&conversoes[marca]&&conversoes[marca][conv]){
const info=conversoes[marca][conv];
document.getElementById('conversao-hint').textContent=info.descricao;
document.getElementById('modelo-hint').textContent=info.requer_modelo?'Modelo necessário para parâmetros cinemáticos':'Modelo usado apenas para nomes no RoboDK';
}
document.getElementById('arquivo').value='';
document.getElementById('pasta').value='';
document.getElementById('detected-badge').style.display='none';
hideStatus();
}
async function selecionarArquivo(){
const marca=document.getElementById('marca').value;
const conv=document.getElementById('conversao').value;
if(!marca||!conv)return;
const extensoes=conversoes[marca][conv].entrada;
const resultado=await window.pywebview.api.selecionar_arquivo(extensoes, marca);
if(resultado.arquivo){
document.getElementById('arquivo').value=resultado.arquivo;
document.getElementById('pasta').value=resultado.pasta;
if(resultado.modelo_detectado){
document.getElementById('modelo').value=resultado.modelo_detectado;
document.getElementById('detected-badge').style.display='inline-block';
}else{
document.getElementById('detected-badge').style.display='none';
}
}
}
async function selecionarPasta(){
const resultado=await window.pywebview.api.selecionar_pasta();
if(resultado)document.getElementById('pasta').value=resultado;
}
async function converter(){
const marca=document.getElementById('marca').value;
const conv=document.getElementById('conversao').value;
const arquivo=document.getElementById('arquivo').value;
const modelo=document.getElementById('modelo').value;
const pasta=document.getElementById('pasta').value;
if(!arquivo){showStatus('Selecione um arquivo primeiro.','error');return;}
if(modelo.startsWith('──')){showStatus('Selecione um modelo válido.','error');return;}
const resultado=await window.pywebview.api.converter(marca,conv,arquivo,modelo,pasta);
showStatus(resultado.sucesso?'✓ '+resultado.mensagem:'✗ '+resultado.mensagem,resultado.sucesso?'success':'error');
}
function showStatus(msg,type){const status=document.getElementById('status');status.textContent=msg;status.className='status '+type;}
function hideStatus(){document.getElementById('status').className='status';}
function toggleTheme(){
  const current=document.body.getAttribute('data-theme')||'light';
  const next=current==='light'?'dark':'light';
  setTheme(next);
  try{ localStorage.setItem('ruki-theme',next); }catch(e){}
}
function setTheme(theme){document.body.setAttribute('data-theme',theme);document.querySelector('.sun-icon').style.display=theme==='dark'?'block':'none';document.querySelector('.moon-icon').style.display=theme==='dark'?'none':'block';}
function openLink(url){window.pywebview.api.open_link(url);}
</script>
</body></html>'''

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================

def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def ler_arquivo(c):
    try:
        with open(c, 'r', encoding='utf-8') as f: return f.readlines()
    except:
        with open(c, 'r', encoding='latin-1') as f: return f.readlines()

def ler_ruki(c):
    with open(c, 'r', encoding='utf-8') as f: return json.load(f)

def get_robot_data(marca, modelo):
    if marca not in DADOS_ROBOS: return None
    d = DADOS_ROBOS[marca]
    return d['robos'].get(modelo, d['robos'].get(d.get('modelo_padrao', '')))

def get_cartesian_pose(target, marca, modelo):
    if target.get('pose_matrix'):
        m = target['pose_matrix']
        if m and len(m) == 4:
            x,y,z = m[0][3]/1000, m[1][3]/1000, m[2][3]/1000
            R = [[m[i][j] for j in range(3)] for i in range(3)]
            trace = R[0][0]+R[1][1]+R[2][2]
            cos_a = max(-1, min(1, (trace-1)/2))
            angle = math.acos(cos_a)
            if abs(angle) < 1e-10: rx,ry,rz = 0,0,0
            elif abs(angle - math.pi) < 1e-10:
                rx = math.sqrt((R[0][0]+1)/2)*math.pi
                ry = math.sqrt((R[1][1]+1)/2)*math.pi
                rz = math.sqrt((R[2][2]+1)/2)*math.pi
                if R[0][1]<0: ry=-ry
                if R[0][2]<0: rz=-rz
            else:
                k = angle/(2*math.sin(angle))
                rx,ry,rz = k*(R[2][1]-R[1][2]), k*(R[0][2]-R[2][0]), k*(R[1][0]-R[0][1])
            return [x,y,z,rx,ry,rz]
    if target.get('pose') and len(target['pose']) >= 6:
        p = target['pose']
        return [p[0]/1000, p[1]/1000, p[2]/1000, deg2rad(p[3]), deg2rad(p[4]), deg2rad(p[5])]
    return None

def detectar_modelo_script(linhas, marca):
    if marca not in DADOS_ROBOS: return None
    texto = '\n'.join(linhas[:100]) if isinstance(linhas, list) else linhas[:5000]
    for modelo in DADOS_ROBOS[marca]['robos'].keys():
        if re.search(re.escape(modelo), texto, re.IGNORECASE): return modelo
    return None

def detectar_modelo_ruki(ruki_data, marca):
    if marca not in DADOS_ROBOS: return None
    robot_name = ruki_data.get('robot', {}).get('name', '')
    if robot_name in DADOS_ROBOS[marca]['robos']: return robot_name
    for modelo in DADOS_ROBOS[marca]['robos'].keys():
        if modelo.upper() in robot_name.upper(): return modelo
    return None

# ==============================================================================
# CONVERSORES
# ==============================================================================

def converter_ruki_para_script(arquivo, marca, modelo, pasta_saida):
    ruki = ler_ruki(arquivo)
    nome = ruki.get('metadata', {}).get('program_name', 'programa')
    ini = ruki.get('program', {}).get('initial_state', {})
    targets = {t['id']: t for t in ruki.get('targets', [])}
    
    linhas = [f"def {nome}():",
              f"  global speed_ms = {ini.get('speed_linear', 500)/1000:.3f}",
              f"  global speed_rads = {deg2rad(ini.get('speed_joints', 60)):.3f}",
              f"  global accel_mss = {ini.get('accel_linear', 2000)/1000:.3f}",
              f"  global accel_radss = {deg2rad(ini.get('accel_joints', 180)):.3f}",
              f"  global blend_radius_m = {ini.get('rounding', 0)/1000:.3f}", ""]
    
    mc = ic = 0
    for step in ruki.get('program', {}).get('steps', []):
        st = step.get('type', '')
        if st == 'MOVE_J':
            t = targets.get(step.get('target'), {})
            j = [deg2rad(x) for x in t.get('joints', [0]*6)]
            linhas.append(f"  movej([{','.join(f'{x:.6f}' for x in j)}],accel_radss,speed_rads,0,blend_radius_m)")
            mc += 1
        elif st == 'MOVE_L':
            t = targets.get(step.get('target'), {})
            pose = get_cartesian_pose(t, marca, modelo)
            if pose:
                linhas.append(f"  movel(p[{','.join(f'{x:.6f}' for x in pose)}],accel_mss,speed_ms,0,blend_radius_m)")
                mc += 1
        elif st == 'SET_IO':
            linhas.append(f"  set_standard_digital_out({step.get('io_index', 0)}, {'True' if step.get('value') else 'False'})")
            ic += 1
        elif st == 'MESSAGE' and step.get('is_comment'):
            linhas.append(f"  # {step.get('text', '')}")
    
    linhas.extend(["end", "", f"{nome}()"])
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{nome}.script")
    with open(caminho, 'w', encoding='utf-8') as f: f.write('\n'.join(linhas))
    return True, f"Convertido!\n\nMovimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

def converter_ruki_para_urp(arquivo, marca, modelo, pasta_saida):
    ruki = ler_ruki(arquivo)
    nome = ruki.get('metadata', {}).get('program_name', 'programa')
    robot = get_robot_data(marca, modelo)
    if not robot: return False, "Dados do robô não encontrados", None
    urp = robot.get('urp', {})
    
    root = ET.Element('URProgram', name=nome, installation="default", directory="/programs", createdIn="5.25.0", lastSavedIn="5.25.0")
    kin = ET.SubElement(root, 'kinematics', status="NOT_INITIALIZED", validChecksum="false")
    for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin, k, value=urp.get(k,''))
    
    children = ET.SubElement(root, 'children')
    ET.SubElement(children, 'InitVariablesNode')
    main_children = ET.SubElement(ET.SubElement(children, 'MainProgram', runOnlyOnce="false", InitVariablesNode="true"), 'children')
    
    targets = {t['id']: t for t in ruki.get('targets', [])}
    mc = ic = wp = 0
    
    for step in ruki.get('program', {}).get('steps', []):
        st = step.get('type', '')
        if st in ['MOVE_J', 'MOVE_L']:
            t = targets.get(step.get('target'), {})
            j = [deg2rad(x) for x in t.get('joints', [0]*6)]
            js = ', '.join(f'{x:.6f}' for x in j)
            motion = "MoveJ" if st == 'MOVE_J' else "MoveL"
            wp += 1
            move = ET.SubElement(main_children, 'Move', motionType=motion, speed="1.0", acceleration="1.2", useActiveTCP="true", positionType="CartesianPose")
            feat = ET.SubElement(move, 'feature')
            feat.set('class', "GeomFeatureReference")
            feat.set('referencedName' if mc==0 else 'reference', "Joint_0_name" if mc==0 else "../../Move/feature")
            mc_el = ET.SubElement(move, 'children')
            wp_el = ET.SubElement(mc_el, 'Waypoint', type="Fixed", name=f"Waypoint_{wp}", kinematicsFlags="4")
            ET.SubElement(wp_el, 'motionParameters')
            pos = ET.SubElement(wp_el, 'position')
            ET.SubElement(pos, 'JointAngles', angles=js)
            ET.SubElement(pos, 'TCPOffset', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            kin2 = ET.SubElement(pos, 'Kinematics', status="NOT_INITIALIZED", validChecksum="false")
            for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin2, k, value=urp.get(k,''))
            ET.SubElement(wp_el, 'BaseToFeature', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            mc += 1
        elif st == 'SET_IO':
            sn = ET.SubElement(main_children, 'Set', type="DigitalOutput")
            pin = ET.SubElement(sn, 'pin')
            pin.set('referencedName' if ic==0 else 'reference', f"digital_out[{step.get('io_index',0)}]" if ic==0 else "../../Set/pin")
            ET.SubElement(sn, 'digitalValue').text = "1" if step.get('value') else "0"
            ic += 1
    
    def indent(e, l=0):
        i = "\n" + "  "*l
        if len(e):
            if not e.text or not e.text.strip(): e.text = i + "  "
            if not e.tail or not e.tail.strip(): e.tail = i
            for c in e: indent(c, l+1)
            if not c.tail or not c.tail.strip(): c.tail = i
        else:
            if l and (not e.tail or not e.tail.strip()): e.tail = i
    indent(root)
    
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{nome}.urp")
    with gzip.open(caminho, 'wt', encoding='utf-8') as f:
        f.write(re.sub(r'\s+/>', '/>', ET.tostring(root, encoding='unicode')))
    return True, f"Convertido!\n\nModelo: {robot.get('nome_completo','')}\nMovimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

def converter_script_para_urp(arquivo, marca, modelo, pasta_saida):
    linhas = ler_arquivo(arquivo)
    nome = os.path.splitext(os.path.basename(arquivo))[0]
    robot = get_robot_data(marca, modelo)
    if not robot: return False, "Dados do robô não encontrados", None
    urp = robot.get('urp', {})
    
    root = ET.Element('URProgram', name=nome, installation="default", directory="/programs", createdIn="5.25.0", lastSavedIn="5.25.0")
    kin = ET.SubElement(root, 'kinematics', status="NOT_INITIALIZED", validChecksum="false")
    for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin, k, value=urp.get(k,''))
    
    children = ET.SubElement(root, 'children')
    ET.SubElement(children, 'InitVariablesNode')
    main_children = ET.SubElement(ET.SubElement(children, 'MainProgram', runOnlyOnce="false", InitVariablesNode="true"), 'children')
    
    mc = ic = wp = 0
    rx_move = re.compile(r'^\s*move([jl])\s*\(\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    rx_io = re.compile(r'set_standard_digital_out\s*\(\s*(\d+)\s*,\s*(True|False|1|0)', re.IGNORECASE)
    
    for linha in linhas:
        ls = linha.strip()
        if not ls or ls.startswith(('#','def ','global ','end')): continue
        m = rx_move.match(ls)
        if m:
            motion = "MoveJ" if m.group(1).lower()=='j' else "MoveL"
            js = m.group(2)
            wp += 1
            move = ET.SubElement(main_children, 'Move', motionType=motion, speed="1.0", acceleration="1.2", useActiveTCP="true", positionType="CartesianPose")
            feat = ET.SubElement(move, 'feature')
            feat.set('class', "GeomFeatureReference")
            feat.set('referencedName' if mc==0 else 'reference', "Joint_0_name" if mc==0 else "../../Move/feature")
            mc_el = ET.SubElement(move, 'children')
            wp_el = ET.SubElement(mc_el, 'Waypoint', type="Fixed", name=f"Waypoint_{wp}", kinematicsFlags="4")
            ET.SubElement(wp_el, 'motionParameters')
            pos = ET.SubElement(wp_el, 'position')
            ET.SubElement(pos, 'JointAngles', angles=js)
            ET.SubElement(pos, 'TCPOffset', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            kin2 = ET.SubElement(pos, 'Kinematics', status="NOT_INITIALIZED", validChecksum="false")
            for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin2, k, value=urp.get(k,''))
            ET.SubElement(wp_el, 'BaseToFeature', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            mc += 1
            continue
        m = rx_io.search(ls)
        if m:
            sn = ET.SubElement(main_children, 'Set', type="DigitalOutput")
            pin = ET.SubElement(sn, 'pin')
            pin.set('referencedName' if ic==0 else 'reference', f"digital_out[{m.group(1)}]" if ic==0 else "../../Set/pin")
            ET.SubElement(sn, 'digitalValue').text = "1" if m.group(2).lower() in ['true','1'] else "0"
            ic += 1
    
    if mc==0 and ic==0: return False, "Nenhum comando encontrado", None
    
    def indent(e, l=0):
        i = "\n" + "  "*l
        if len(e):
            if not e.text or not e.text.strip(): e.text = i + "  "
            if not e.tail or not e.tail.strip(): e.tail = i
            for c in e: indent(c, l+1)
            if not c.tail or not c.tail.strip(): c.tail = i
        else:
            if l and (not e.tail or not e.tail.strip()): e.tail = i
    indent(root)
    
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{nome}.urp")
    with gzip.open(caminho, 'wt', encoding='utf-8') as f:
        f.write(re.sub(r'\s+/>', '/>', ET.tostring(root, encoding='unicode')))
    return True, f"Convertido!\n\nMovimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

def converter_script_para_robodk(arquivo, marca, modelo, pasta_saida):
    linhas = ler_arquivo(arquivo)
    nome = os.path.splitext(os.path.basename(arquivo))[0].replace(' ', '_')
    robot = get_robot_data(marca, modelo)
    nome_robo = robot.get('robodk_nome', modelo) if robot else modelo
    nome_frame = robot.get('robodk_frame', f'{nome_robo} Base') if robot else f'{modelo} Base'
    
    codigo = f'''# -*- coding: UTF-8 -*-
from robolink import *
from robodk import *

RDK = Robolink()
robot = RDK.Item('{nome_robo}', ITEM_TYPE_ROBOT)
robot.setPoseFrame(RDK.Item('{nome_frame}', ITEM_TYPE_FRAME))
robot.setPoseTool(RDK.Item('Tool', ITEM_TYPE_TOOL))
robot.setSpeed(250)
robot.setSpeedJoints(60)

'''
    
    mc = ic = 0
    rx_move = re.compile(r'move([jl])\s*\(\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    rx_io = re.compile(r'set_standard_digital_out\s*\(\s*(\d+)\s*,\s*(True|False|1|0)', re.IGNORECASE)
    
    for linha in linhas:
        ls = linha.strip()
        if not ls or ls.startswith(('#', 'def ', 'global ', 'end')): continue
        m = rx_move.search(ls)
        if m:
            tipo = 'MoveJ' if m.group(1).lower() == 'j' else 'MoveL'
            try:
                vals = [float(v.strip()) for v in m.group(2).split(',')][:6]
                if all(abs(v) < 7 for v in vals): vals = [rad2deg(v) for v in vals]
                codigo += f"robot.{tipo}([{', '.join(f'{v:.4f}' for v in vals)}])\n"
                mc += 1
            except: pass
            continue
        m = rx_io.search(ls)
        if m:
            codigo += f"robot.setDO({m.group(1)}, {1 if m.group(2).lower() in ['true', '1'] else 0})\n"
            ic += 1
    
    codigo += '\nprint("Programa concluído!")\n'
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{nome}_RoboDK.py")
    with open(caminho, 'w', encoding='utf-8') as f: f.write(codigo)
    return True, f"Convertido!\n\nMovimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

# Dicionário de conversões
CONVERSOES = {marca: em.CONVERSOES for marca, em in EMITTERS.items()}

# ==============================================================================
# API PYWEBVIEW
# ==============================================================================

class Api:
    def get_dados(self):
        # Emitters (v1.1) não são obrigados a ter a chave 'saida'. A UI só precisa
        # de: entrada, descricao, requer_modelo.
        return {
            'robos': DADOS_ROBOS,
            'conversoes': {
                m: {
                    c: {
                        'entrada': i.get('entrada', ['.*']),
                        'descricao': i.get('descricao', ''),
                        'requer_modelo': bool(i.get('requer_modelo', False)),
                    }
                    for c, i in cs.items()
                }
                for m, cs in CONVERSOES.items()
            }
        }
    
    def selecionar_arquivo(self, extensoes, marca):
        # pywebview espera file_types como tupla de STRINGS no formato:
        #   'Descricao (*.ext;*.ext2)'
        # (lista de tuples quebra com TypeError; filtro malformado vira ValueError)
        extensoes = extensoes or []
        patterns = []

        for e in extensoes:
            e = str(e).strip()
            if not e:
                continue
            if e in ('*', '*.*', '.*'):
                continue

            if e.startswith('*.'):
                pat = e
            elif e.startswith('.'):
                pat = f'*{e}'       # '.ruki' -> '*.ruki'
            else:
                pat = f'*.{e}'      # 'ruki'  -> '*.ruki'

            patterns.append(pat)

        if patterns:
            pats = ';'.join(sorted(set(patterns)))
            ft = (f'Arquivos suportados ({pats})', 'All files (*.*)')
        else:
            ft = ('All files (*.*)',)

        resultado = window.create_file_dialog(webview.OPEN_DIALOG, file_types=ft)

        if resultado and len(resultado) > 0:
            arq = resultado[0]
            pasta = os.path.dirname(arq)

            modelo = None
            if marca and marca in DADOS_ROBOS:
                try:
                    em = EMITTERS.get(marca)
                    if em and hasattr(em, 'detectar_modelo'):
                        modelo = em.detectar_modelo(arq, DADOS_ROBOS[marca]['robos'])
                    else:
                        if arq.endswith('.ruki'):
                            modelo = detectar_modelo_ruki(ler_ruki(arq), marca)
                        else:
                            modelo = detectar_modelo_script(ler_arquivo(arq), marca)
                except:
                    pass

            return {'arquivo': arq, 'pasta': pasta, 'modelo_detectado': modelo}

        return {'arquivo': None, 'pasta': None, 'modelo_detectado': None}

    
    def selecionar_pasta(self):
        resultado = window.create_file_dialog(webview.FOLDER_DIALOG)
        return resultado[0] if resultado and len(resultado) > 0 else None
    
    def converter(self, marca, conv, arquivo, modelo, pasta):
        ok, msg, _ = executar_conversao(marca, conv, arquivo, modelo, pasta)
        return {"sucesso": ok, "mensagem": msg}
    
    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)

# ==============================================================================
# MAIN
# ==============================================================================

window = None

def main():
    global window
    
    # Importa webview aqui para mostrar erro melhor
    try:
        import webview
    except ImportError:
        print("\n" + "!" * 50)
        print("ERRO: pywebview não está instalado!")
        print("Execute: pip install pywebview")
        print("!" * 50)
        input("\nPressione Enter para sair...")
        return
    
    # Verifica se ícone existe
    icon = ICON_PATH if os.path.exists(ICON_PATH) else None
    if not icon:
        print(f"Aviso: Ícone não encontrado em {ICON_PATH}")
    
    api = Api()
    window = webview.create_window(
        f'Ruki-C v{RUKI_VERSION}', 
        html=HTML_TEMPLATE, 
        js_api=api, 
        width=480, 
        height=660,
    )
    
    # Inicia com ou sem ícone
    if icon:
        webview.start(icon=icon)
    else:
        webview.start()

if __name__ == "__main__":
    try:
        import webview
        main()
    except ImportError:
        print("\n" + "!" * 50)
        print("ERRO: pywebview não está instalado!")
        print("Execute: pip install pywebview")
        print("!" * 50)
        input("\nPressione Enter para sair...")
    except Exception as e:
        print(f"\nERRO: {e}")
        traceback.print_exc()
        input("\nPressione Enter para sair...")
