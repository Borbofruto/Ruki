# -*- coding: UTF-8 -*-
from robodk import robolink

# 1. TRATAMENTO DE CONSTANTES (Blindagem contra erro de Import)
try:
    from robodk.robodk import ITEM_TYPE_ROBOT
except ImportError:
    try:
        from robodk.robolink import ITEM_TYPE_ROBOT
    except ImportError:
        ITEM_TYPE_ROBOT = 1 # Fallback manual

import socket
import time

# ==========================================
# CONFIGURAÇÕES
# ==========================================
ROBOT_NAME = 'UR20' 
UNITY_IP   = '127.0.0.1'
UNITY_PORT = 20505

# ==========================================
# INICIALIZAÇÃO DO ROBODK
# ==========================================
RDK = robolink.Robolink()

# 2. TRATAMENTO DO MÉTODO DE BUSCA (Blindagem contra AttributeError)
# Tenta usar o método novo (getItem), se falhar, usa o antigo (Item)
try:
    if hasattr(RDK, 'getItem'):
        robot = RDK.getItem(ROBOT_NAME, ITEM_TYPE_ROBOT)
    else:
        robot = RDK.Item(ROBOT_NAME, ITEM_TYPE_ROBOT)
except Exception as e:
    # Última tentativa desesperada usando apenas o nome (sem tipo)
    print(f"Aviso: Tentando buscar '{ROBOT_NAME}' sem filtro de tipo...")
    robot = RDK.Item(ROBOT_NAME)

# 3. VALIDAÇÃO
if not robot.Valid():
    print(f"ERRO CRÍTICO: Robô '{ROBOT_NAME}' não encontrado!")
    print("Itens disponíveis na estação:")
    # Tenta listar itens (compatibilidade com ItemList)
    lista_itens = RDK.ItemList() if hasattr(RDK, 'ItemList') else []
    for item in lista_itens:
        print(f" - {item.Name()}")
    exit()

print(f"--> SUCESSO: Robô '{robot.Name()}' conectado.")

def iniciar_stream():
    print(f"--> Tentando conectar ao Unity em {UNITY_IP}:{UNITY_PORT}...")
    
    while True:
        try:
            # Cria o socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((UNITY_IP, UNITY_PORT))
            print("--> CONEXÃO ESTABELECIDA COM UNITY!")

            while True:
                # 1. PEGAR JUNTAS
                joints = robot.Joints().list()
                
                # 2. LÓGICA DE EVENTO (Filhos/Attach)
                # Verifica compatibilidade do método Childs
                if hasattr(robot, 'Childs'):
                    children = robot.Childs()
                    has_child = 1 if (children and len(children) > 0) else 0
                else:
                    has_child = 0 # Ignora se a API for muito antiga

                # 3. FORMATAR E ENVIAR
                msg = ",".join(f"{j:.4f}" for j in joints) + f",{has_child}\n"
                print(f"Enviando: {msg}")
                sock.sendall(msg.encode('utf-8'))
                
                time.sleep(0.01) # 100Hz
                
        except (socket.error, ConnectionRefusedError):
            print("Aguardando servidor do Unity (Tentando em 2s)...")
            time.sleep(2)
        except Exception as e:
            print(f"Erro na transmissão: {e}")
            time.sleep(1)
        finally:
            sock.close()

if __name__ == "__main__":
    iniciar_stream()