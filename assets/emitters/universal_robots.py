# -*- coding: UTF-8 -*-
"""
Ruki Emitter - Universal Robots v1.6
CORRIGIDO: MoveL agora usa pose cartesiana corretamente (não depende de #JOINTS)
"""

import os, json, gzip, re, math
import xml.etree.ElementTree as ET

def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def ler_arquivo(c):
    try:
        with open(c, 'r', encoding='utf-8') as f: return f.readlines()
    except:
        with open(c, 'r', encoding='latin-1') as f: return f.readlines()

def ler_ruki(c):
    with open(c, 'r', encoding='utf-8') as f: return json.load(f)

def get_cartesian_pose(target):
    """Extrai pose cartesiana (metros + rotation vector em rad)"""
    if target.get('pose_matrix'):
        m = target['pose_matrix']
        if m and len(m) == 4:
            x, y, z = m[0][3]/1000, m[1][3]/1000, m[2][3]/1000
            R = [[m[i][j] for j in range(3)] for i in range(3)]
            trace = R[0][0] + R[1][1] + R[2][2]
            cos_a = max(-1, min(1, (trace - 1) / 2))
            angle = math.acos(cos_a)
            if abs(angle) < 1e-10: rx, ry, rz = 0, 0, 0
            elif abs(angle - math.pi) < 1e-10:
                rx = math.sqrt((R[0][0]+1)/2) * math.pi
                ry = math.sqrt((R[1][1]+1)/2) * math.pi
                rz = math.sqrt((R[2][2]+1)/2) * math.pi
                if R[0][1] < 0: ry = -ry
                if R[0][2] < 0: rz = -rz
            else:
                k = angle / (2 * math.sin(angle))
                rx, ry, rz = k*(R[2][1]-R[1][2]), k*(R[0][2]-R[2][0]), k*(R[1][0]-R[0][1])
            return [x, y, z, rx, ry, rz]
    if target.get('pose') and len(target['pose']) >= 6:
        p = target['pose']
        return [p[0]/1000, p[1]/1000, p[2]/1000, deg2rad(p[3]), deg2rad(p[4]), deg2rad(p[5])]
    return None

def detectar_modelo(arquivo, robos):
    """Detecta modelo UR do arquivo"""
    try:
        if arquivo.endswith('.ruki'):
            data = ler_ruki(arquivo)
            nome = data.get('robot', {}).get('name', '')
            for m in robos.keys():
                if m in nome or m.upper() in nome.upper(): return m
        else:
            texto = '\n'.join(ler_arquivo(arquivo)[:100])
            for m in robos.keys():
                if re.search(r'\b' + re.escape(m) + r'\b', texto, re.IGNORECASE): return m
    except: pass
    return None

def parse_script_moves(linhas):
    """
    Parser para URScript.
    MoveJ: retorna joints
    MoveL: retorna joints do #JOINTS:[...] se disponível, senão pose cartesiana
    """
    comandos = []
    
    rx_movej = re.compile(r'movej\s*\(\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    rx_movel_p = re.compile(r'movel\s*\(\s*p\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    rx_movel_pose_trans = re.compile(r'movel\s*\(.*?p\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    rx_movel_array = re.compile(r'movel\s*\(\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)
    # Regex para #JOINTS - aceita ] ou ) como fechamento (RoboDK às vezes usa ) no final)
    rx_joints_comment = re.compile(r'#\s*JOINTS\s*:\s*\[\s*([^\]\)]+)\s*[\]\)]', re.IGNORECASE)
    rx_io = re.compile(r'set_standard_digital_out\s*\(\s*(\d+)\s*,\s*(True|False|1|0)', re.IGNORECASE)
    
    for linha in linhas:
        ls = linha.strip()
        if not ls or ls.startswith(('def ', 'global ', 'end')): continue
        # Não pula linhas com # se tiver #JOINTS
        if ls.startswith('#') and '#JOINTS' not in ls.upper(): continue
        
        # Primeiro verifica se tem #JOINTS no comentário (para MoveJ e MoveL)
        joints_from_comment = None
        jc = rx_joints_comment.search(ls)
        if jc:
            try:
                joints_from_comment = [float(v.strip().rstrip(')')) for v in jc.group(1).split(',')][:6]
                # Converte rad para deg se parecer estar em radianos
                if all(abs(v) < 7 for v in joints_from_comment):
                    joints_from_comment = [rad2deg(v) for v in joints_from_comment]
            except:
                joints_from_comment = None
        
        # MoveJ
        m = rx_movej.search(ls)
        if m:
            try:
                vals = [float(v.strip()) for v in m.group(1).split(',')][:6]
                if all(abs(v) < 7 for v in vals): vals = [rad2deg(v) for v in vals]
                # Usa #JOINTS se disponível (mais preciso), senão usa os valores do movej
                comandos.append({'cmd': 'move', 'tipo': 'MoveJ', 'joints': joints_from_comment or vals})
            except: pass
            continue
        
        # MoveL
        m = rx_movel_p.search(ls)
        if not m: m = rx_movel_pose_trans.search(ls)
        if not m: m = rx_movel_array.search(ls)
        
        if m:
            try:
                pose_vals = [float(v.strip()) for v in m.group(1).split(',')][:6]
            except:
                pose_vals = None
            
            if joints_from_comment:
                # Tem #JOINTS - usa para .urp e .py
                comandos.append({'cmd': 'move', 'tipo': 'MoveL', 'joints': joints_from_comment, 'pose': pose_vals})
            elif pose_vals:
                # Só tem pose - funciona para .py, mas não para .urp
                comandos.append({'cmd': 'move', 'tipo': 'MoveL', 'pose': pose_vals})
            continue
        
        # IO
        m = rx_io.search(ls)
        if m:
            comandos.append({'cmd': 'io', 'index': int(m.group(1)), 'value': m.group(2).lower() in ['true', '1']})
    
    return comandos

def ruki_para_script(arquivo, robot_data, pasta):
    """Converte .ruki → .script"""
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
            pose = get_cartesian_pose(t)
            if pose:
                linhas.append(f"  movel(p[{','.join(f'{x:.6f}' for x in pose)}],accel_mss,speed_ms,0,blend_radius_m)")
                mc += 1
        elif st == 'SET_IO':
            linhas.append(f"  set_standard_digital_out({step.get('io_index', 0)}, {'True' if step.get('value') else 'False'})")
            ic += 1
        elif st == 'MESSAGE' and step.get('is_comment'):
            linhas.append(f"  # {step.get('text', '')}")
    
    linhas.extend(["end", "", f"{nome}()"])
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{nome}.script")
    with open(caminho, 'w', encoding='utf-8') as f: f.write('\n'.join(linhas))
    return True, f"Movimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

def ruki_para_urp(arquivo, robot_data, pasta):
    """Converte .ruki → .urp"""
    ruki = ler_ruki(arquivo)
    nome = ruki.get('metadata', {}).get('program_name', 'programa')
    if not robot_data: return False, "Dados do robô não encontrados", None
    urp = robot_data.get('urp', {})
    
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
    
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{nome}.urp")
    with gzip.open(caminho, 'wt', encoding='utf-8') as f:
        f.write(re.sub(r'\s+/>', '/>', ET.tostring(root, encoding='unicode')))
    return True, f"Modelo: {robot_data.get('nome_completo','')}\nMovimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

def script_para_urp(arquivo, robot_data, pasta):
    """
    Converte .script → .urp
    REQUER: .script do RoboDK com #JOINTS:[...] nos comentários
    """
    linhas = ler_arquivo(arquivo)
    nome = os.path.splitext(os.path.basename(arquivo))[0]
    if not robot_data: return False, "Dados do robô não encontrados", None
    urp = robot_data.get('urp', {})
    
    comandos = parse_script_moves(linhas)
    
    root = ET.Element('URProgram', name=nome, installation="default", directory="/programs", createdIn="5.25.0", lastSavedIn="5.25.0")
    kin = ET.SubElement(root, 'kinematics', status="NOT_INITIALIZED", validChecksum="false")
    for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin, k, value=urp.get(k,''))
    
    children = ET.SubElement(root, 'children')
    ET.SubElement(children, 'InitVariablesNode')
    main_children = ET.SubElement(ET.SubElement(children, 'MainProgram', runOnlyOnce="false", InitVariablesNode="true"), 'children')
    
    mc = ic = wp = 0
    movel_sem_joints = 0
    
    for cmd in comandos:
        if cmd['cmd'] == 'move':
            # Para .urp, SEMPRE precisamos de joints (tanto MoveJ quanto MoveL)
            if 'joints' not in cmd:
                movel_sem_joints += 1
                continue
            
            wp += 1
            motion = cmd['tipo']
            j = [deg2rad(x) for x in cmd['joints']]
            
            move = ET.SubElement(main_children, 'Move', motionType=motion, speed="1.0", acceleration="1.2", useActiveTCP="true", positionType="CartesianPose")
            feat = ET.SubElement(move, 'feature')
            feat.set('class', "GeomFeatureReference")
            feat.set('referencedName' if mc==0 else 'reference', "Joint_0_name" if mc==0 else "../../Move/feature")
            mc_el = ET.SubElement(move, 'children')
            wp_el = ET.SubElement(mc_el, 'Waypoint', type="Fixed", name=f"Waypoint_{wp}", kinematicsFlags="4")
            ET.SubElement(wp_el, 'motionParameters')
            pos = ET.SubElement(wp_el, 'position')
            ET.SubElement(pos, 'JointAngles', angles=', '.join(f'{x:.6f}' for x in j))
            ET.SubElement(pos, 'TCPOffset', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            kin2 = ET.SubElement(pos, 'Kinematics', status="NOT_INITIALIZED", validChecksum="false")
            for k in ['deltaTheta','a','d','alpha','jointChecksum']: ET.SubElement(kin2, k, value=urp.get(k,''))
            ET.SubElement(wp_el, 'BaseToFeature', pose="0.0, 0.0, 0.0, 0.0, 0.0, 0.0")
            mc += 1
            
        elif cmd['cmd'] == 'io':
            sn = ET.SubElement(main_children, 'Set', type="DigitalOutput")
            pin = ET.SubElement(sn, 'pin')
            pin.set('referencedName' if ic==0 else 'reference', f"digital_out[{cmd['index']}]" if ic==0 else "../../Set/pin")
            ET.SubElement(sn, 'digitalValue').text = "1" if cmd['value'] else "0"
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
    
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{nome}.urp")
    with gzip.open(caminho, 'wt', encoding='utf-8') as f:
        f.write(re.sub(r'\s+/>', '/>', ET.tostring(root, encoding='unicode')))
    
    msg = f"Movimentos: {mc}\nIOs: {ic}"
    if movel_sem_joints > 0:
        msg += f"\n\n⚠ {movel_sem_joints} MoveL ignorados (sem #JOINTS)\nUse .script do RoboDK com output joints+cartesian"
    return True, msg + f"\n\nArquivo: {caminho}", caminho

def script_para_robodk(arquivo, robot_data, pasta):
    """Converte .script → .py (MoveL usa pose cartesiana ou joints)"""
    linhas = ler_arquivo(arquivo)
    nome = os.path.splitext(os.path.basename(arquivo))[0].replace(' ','_')
    nome_robo = robot_data.get('robodk_nome','UR20') if robot_data else 'UR20'
    nome_frame = robot_data.get('robodk_frame',f'{nome_robo} Base') if robot_data else 'UR20 Base'
    
    comandos = parse_script_moves(linhas)
    
    # Configurações PRIMEIRO (o que o usuário precisa editar)
    codigo = f'''# -*- coding: UTF-8 -*-
"""
Programa RoboDK gerado por Ruki-C v1.7
Arquivo origem: {os.path.basename(arquivo)}
"""

from robolink import *
from robodk import *
import math

# ============================================================
# CONFIGURAÇÕES DO ROBÔ (edite conforme necessário)
# ============================================================
RDK = Robolink()
robot = RDK.Item('{nome_robo}', ITEM_TYPE_ROBOT)
robot.setPoseFrame(RDK.Item('{nome_frame}', ITEM_TYPE_FRAME))
robot.setPoseTool(RDK.Item('Tool', ITEM_TYPE_TOOL))
robot.setSpeed(250)
robot.setSpeedJoints(60)

# ============================================================
# FUNÇÃO AUXILIAR (não precisa editar)
# ============================================================
def ur_pose_to_robodk(x, y, z, rx, ry, rz):
    """Converte pose UR (metros + rotation vector rad) para Pose RoboDK"""
    x_mm, y_mm, z_mm = x * 1000, y * 1000, z * 1000
    angle = math.sqrt(rx*rx + ry*ry + rz*rz)
    if angle < 1e-10:
        return KUKA_2_Pose([x_mm, y_mm, z_mm, 0, 0, 0])
    kx, ky, kz = rx/angle, ry/angle, rz/angle
    c, s = math.cos(angle), math.sin(angle)
    v = 1 - c
    R = [[kx*kx*v+c, kx*ky*v-kz*s, kx*kz*v+ky*s],
         [kx*ky*v+kz*s, ky*ky*v+c, ky*kz*v-kx*s],
         [kx*kz*v-ky*s, ky*kz*v+kx*s, kz*kz*v+c]]
    if abs(R[2][0]) < 0.9999:
        pitch = math.asin(-R[2][0])
        roll = math.atan2(R[2][1]/math.cos(pitch), R[2][2]/math.cos(pitch))
        yaw = math.atan2(R[1][0]/math.cos(pitch), R[0][0]/math.cos(pitch))
    else:
        yaw = 0
        if R[2][0] < 0:
            pitch = math.pi/2
            roll = math.atan2(R[0][1], R[0][2])
        else:
            pitch = -math.pi/2
            roll = math.atan2(-R[0][1], -R[0][2])
    return KUKA_2_Pose([x_mm, y_mm, z_mm, math.degrees(yaw), math.degrees(pitch), math.degrees(roll)])

# ============================================================
# PROGRAMA
# ============================================================
'''
    
    mc = ic = 0
    for cmd in comandos:
        if cmd['cmd'] == 'move':
            if cmd['tipo'] == 'MoveJ' and 'joints' in cmd:
                codigo += f"robot.MoveJ([{', '.join(f'{v:.4f}' for v in cmd['joints'])}])\n"
                mc += 1
            elif cmd['tipo'] == 'MoveL':
                if 'pose' in cmd:
                    # Usa pose cartesiana (preferível para MoveL)
                    p = cmd['pose']
                    codigo += f"robot.MoveL(ur_pose_to_robodk({p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f}, {p[3]:.6f}, {p[4]:.6f}, {p[5]:.6f}))\n"
                    mc += 1
                elif 'joints' in cmd:
                    # Fallback para joints se não tiver pose
                    codigo += f"robot.MoveL([{', '.join(f'{v:.4f}' for v in cmd['joints'])}])\n"
                    mc += 1
        elif cmd['cmd'] == 'io':
            codigo += f"robot.setDO({cmd['index']}, {1 if cmd['value'] else 0})\n"
            ic += 1
    
    codigo += '\nprint("Programa concluído!")\n'
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{nome}_RoboDK.py")
    with open(caminho, 'w', encoding='utf-8') as f: f.write(codigo)
    return True, f"Movimentos: {mc}\nIOs: {ic}\n\nArquivo: {caminho}", caminho

CONVERSOES = {
    '.ruki → .script': {'entrada':['.ruki'], 'descricao':'Converte IR (.ruki) para URScript', 'conversor':ruki_para_script, 'requer_modelo':True},
    '.ruki → .urp': {'entrada':['.ruki'], 'descricao':'Converte IR (.ruki) para Polyscope/URSim', 'conversor':ruki_para_urp, 'requer_modelo':True},
    '.script → .urp': {'entrada':['.script'], 'descricao':'Converte URScript para Polyscope/URSim', 'conversor':script_para_urp, 'requer_modelo':True},
    '.script → .py': {'entrada':['.script'], 'descricao':'Converte URScript para RoboDK Python', 'conversor':script_para_robodk, 'requer_modelo':False},
}
