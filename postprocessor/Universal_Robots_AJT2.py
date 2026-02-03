# -*- coding: UTF-8 -*-
# Copyright 2015-2025 - RoboDK - https://robodk.com/
#
# MODIFICADO: 
#   1. Adiciona informações de juntas como comentário (#JOINTS) para o conversor .script → .urp
#   2. DESABILITA a geração automática do .urp (que não funciona corretamente)
#
# Baseado no Universal_Robots.py original
#
# More information about RoboDK Post Processors:
#     https://robodk.com/doc/en/Post-Processors.html#SelectPost
#     https://robodk.com/doc/en/PythonAPI/postprocessor.html
# ----------------------------------------------------

import sys
import os
import math
from robodk import *

# Detect Python version and post processor path
print("Using Python version: " + str(sys.version_info))
print("RoboDK Post Processor: " + __file__)

# Load the post processor from libspp
try:
    from libspp.Universal_Robots import RobotPost as MainPost

except Exception as e:
    import traceback
    msg = "Invalid Python version or post processor not found. Make sure to download the latest version of RoboDK."
    msg += "\nSelect Tools-Options-Python and select a supported Python version"
    msg += "\nThis script was executed using Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
    msg += "\nInformation about the error:\n" + repr(e)
    msg += "\n" + traceback.format_exc()
    print(msg)
    raise Exception(msg)


def _deg2rad(deg):
    """Converte graus para radianos"""
    return deg * math.pi / 180.0


class RobotPost(MainPost):

    # ------------------------ Customize your RoboDK post processor using the following variables ------------------------

    # ============================================================================
    # CONFIGURAÇÃO CUSTOMIZADA - NÃO GERAR .URP
    # ============================================================================
    # Se True, NÃO gera o arquivo .urp (só gera o .script)
    # Use o Conversor_Script_para_URP.py para gerar um .urp funcional
    SKIP_URP_GENERATION = True
    
    # ============================================================================

    # Include custom header to program.
    INCLUDE_HEADER = True

    # Set to True to use MoveP, set to False to use MoveL
    USE_MOVEP = False

    # Set to True to use the reference frame as a pose and pose_trans to premultiply all targets
    # Set to False to output all targets with respect to the robot base
    USE_RELATIVE_TARGETS = True

    # If True, it will attempt to upload using SFTP. It requires PYSFTP (pip install pysftp. Important: It requires Visual Studio Community C++ 10.0)
    UPLOAD_SFTP = False

    # Set True to automatically filter blending (CB3 or prior), set to False to leave it up to the controller to adjust the blending as needed
    # Leave this to default (None) to automatically detect the appropriate action
    BLENDING_CHECK = None

    # Force accurate move before we trigger program calls, speed changes or changing digital outputs
    MOVE_ACCURATE_CALLS = True

    # default speed for linear moves in m/s
    SPEED_MS       = 0.250

    # default speed for joint moves in rad/s
    SPEED_RADS     = 0.75

    # default acceleration for lineaer moves in m/ss
    ACCEL_MSS      = 1.2

    # default acceleration for joint moves in rad/ss
    ACCEL_RADSS    = 1.2

    # default blend radius in meters (corners smoothing)
    BLEND_RADIUS_M = 0.001

    # 5000    # Maximum number of lines per program. If the number of lines is exceeded, the program will be executed step by step by RoboDK
    MAX_LINES_X_PROG = 1e9

    # minimum circle radius to output (in mm). It does not take into account the Blend radius
    MOVEC_MIN_RADIUS = 1

    # maximum circle radius to output (in mm). It does not take into account the Blend radius
    MOVEC_MAX_RADIUS = 10000

    # Maximum speeds and accelerations allowed by the controller (otherwise it throws a speed error)
    MAX_SPEED_MS = 3.0
    MAX_SPEED_DEGS = 180
    MAX_ACCEL_MSS = 15.0
    MAX_ACCEL_DEGSS = 2291.8

    # --------------------------------------------------------------------------------------------------------------------
    # NOVO: Armazena as últimas juntas para adicionar ao comentário
    _last_joints_rad = None
    _last_speed = None
    _last_accel = None
    # --------------------------------------------------------------------------------------------------------------------

    def MoveJ(self, pose, joints, conf_RLF=None):
        """MoveJ - Salva as juntas e chama o método original"""
        if joints is not None and len(joints) >= 6:
            # Converte para radianos e armazena
            self._last_joints_rad = [_deg2rad(j) for j in joints[:6]]
        
        # Chama o método original
        super().MoveJ(pose, joints, conf_RLF)
        
        # Adiciona comentário com juntas na última linha adicionada
        if self._last_joints_rad is not None:
            self._append_joints_comment()

    def MoveL(self, pose, joints, conf_RLF=None):
        """MoveL - Salva as juntas e chama o método original"""
        if joints is not None and len(joints) >= 6:
            # Converte para radianos e armazena
            self._last_joints_rad = [_deg2rad(j) for j in joints[:6]]
        
        # Chama o método original
        super().MoveL(pose, joints, conf_RLF)
        
        # Adiciona comentário com juntas na última linha adicionada
        if self._last_joints_rad is not None:
            self._append_joints_comment()

    def MoveC(self, pose1, joints1, pose2, joints2, conf_RLF_1=None, conf_RLF_2=None):
        """MoveC - Salva as juntas e chama o método original"""
        # Armazena juntas do ponto final
        if joints2 is not None and len(joints2) >= 6:
            self._last_joints_rad = [_deg2rad(j) for j in joints2[:6]]
        
        # Chama o método original
        super().MoveC(pose1, joints1, pose2, joints2, conf_RLF_1, conf_RLF_2)
        
        # Adiciona comentário com juntas
        if self._last_joints_rad is not None:
            self._append_joints_comment()

    def _append_joints_comment(self):
        """
        Adiciona as juntas como comentário na última linha do programa.
        Formato: #JOINTS:[j1,j2,j3,j4,j5,j6]
        """
        if self._last_joints_rad is None:
            return
        
        try:
            # Acessa a última linha do programa
            if hasattr(self, 'PROG') and self.PROG:
                # Formata as juntas com 6 casas decimais
                joints_str = ",".join(["%.6f" % j for j in self._last_joints_rad])
                comment = " #JOINTS:[%s]" % joints_str
                
                # Adiciona o comentário à última linha
                self.PROG[-1] = self.PROG[-1].rstrip() + comment
        except Exception as e:
            # Se falhar, não quebra nada - apenas ignora
            pass
        
        # Limpa para o próximo movimento
        self._last_joints_rad = None

    # --------------------------------------------------------------------------------------------------------------------
    # OVERRIDE: ProgSave - Intercepta a gravação para não gerar .urp
    # --------------------------------------------------------------------------------------------------------------------
    
    def ProgSave(self, folder, progname, ask_user=False, show_result=False):
        """
        Sobrescreve o método de salvamento para:
        1. Gerar o .script normalmente
        2. NÃO gerar o .urp (se SKIP_URP_GENERATION = True)
        """
        # Chama o método original que gera os arquivos
        result = super().ProgSave(folder, progname, ask_user, show_result)
        
        # Se configurado para pular .urp, deleta o arquivo gerado
        if self.SKIP_URP_GENERATION:
            try:
                urp_path = os.path.join(folder, progname + ".urp")
                if os.path.exists(urp_path):
                    os.remove(urp_path)
                    print(f"[INFO] Arquivo .urp removido: {urp_path}")
                    print(f"[INFO] Use o Conversor_Script_para_URP.py para gerar um .urp funcional")
            except Exception as e:
                print(f"[AVISO] Não foi possível remover .urp: {e}")
        
        return result

    # --------------------------------------------------------------------------------------------------------------------
    # Mantém as customizações originais de IO
    # --------------------------------------------------------------------------------------------------------------------

    def setDigital(self, io_var, io_value):
        if isinstance(io_var, str):
            self.addline('%s = %s' % (io_var, io_value))
        else:
            estado = "True" if (io_value == 1 or io_value == "1") else "False"
            self.addline('set_standard_digital_out(%s, %s)' % (io_var, estado))

    def setWaitDI(self, io_var, io_value, timeout_ms=-1):
        estado = "True" if (io_value == 1 or io_value == "1") else "False"
        if timeout_ms < 0:
            self.addline('while (get_standard_digital_in(%s) != %s):' % (io_var, estado))
            self.addline('  sync()')
            self.addline('end')
        else:
            timeout_s = timeout_ms / 1000.0
            self.addline('while (get_standard_digital_in(%s) != %s):' % (io_var, estado))
            self.addline('  sync()')
            self.addline('end')

    # --------------------------------------------------------------------------------------------------------------------

if __name__== "__main__":
    try:
        from libspp.Universal_Robots import test_post
        test_post()
    except:
        print("Post processor carregado com sucesso!")
        print("Coloque este arquivo em C:/RoboDK/Posts/")
        print("")
        print("Configuração atual:")
        print(f"  SKIP_URP_GENERATION = True (não gera .urp)")
        print("")
        print("Use o Conversor_Script_para_URP.py para converter o .script em .urp")
