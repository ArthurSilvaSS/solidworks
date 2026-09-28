"""
Sistema de Log do Controle CAD.
Gera entradas legíveis para auditoria em controle_cad.log e registra detalhes técnicos.
"""

import os
import sys
import logging
from datetime import datetime

# Diretório raiz da aplicação
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "controle_cad.log")

logger = logging.getLogger("ControleCAD")
logger.setLevel(logging.INFO)

# Formatter para console/detalhes
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(console_handler)


def registrar_log(acao: str, detalhes: dict, nivel: str = "INFO"):
    """
    Registra um evento formatado no arquivo controle_cad.log.
    
    Exemplo de formato gerado:
    15/09/2026 08:30
    PROJETO CRIADO
    Código: 250.001
    Nome: Parafuso
    Usuário: Arthur
    """
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    linhas = [f"\n{timestamp}", acao.upper()]
    for chave, valor in detalhes.items():
        linhas.append(f"{chave}: {valor}")
    linhas.append("-" * 40)
    
    mensagem_formatada = "\n".join(linhas) + "\n"
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(mensagem_formatada)
    except Exception as e:
        logger.error(f"Erro ao gravar no arquivo de log: {e}")
        
    if nivel == "ERROR":
        logger.error(f"{acao}: {detalhes}")
    elif nivel == "WARNING":
        logger.warning(f"{acao}: {detalhes}")
    else:
        logger.info(f"{acao}: {detalhes}")
