"""
Gerenciador de Configurações do Controle CAD.
Lê e grava parâmetros no arquivo config.json.
"""

import json
import os
from typing import Dict, Any

# Diretório raiz da aplicação (onde está o projeto)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

CONFIG_PADRAO: Dict[str, Any] = {
    "pasta_raiz": os.path.join(BASE_DIR, "Engenharia_Projetos"),
    "solidworks_automatico": True,
    "criar_pdf": True,
    "monitorar_pasta": True,
    "template_peca": "",
    "template_montagem": "",
    "template_desenho": "",
    "templates_desenho_linhas": {
        "MedicalFix": "",
        "DentFix": "",
        "TraumaFix": ""
    },
    "modo_simulacao_sw": False
}


def carregar_config() -> Dict[str, Any]:
    """Carrega as configurações do config.json ou cria com valores padrão."""
    if not os.path.exists(CONFIG_FILE):
        salvar_config(CONFIG_PADRAO)
        return CONFIG_PADRAO.copy()
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            # Garante que novas chaves existentes no padrão estejam presentes
            for k, v in CONFIG_PADRAO.items():
                if k not in dados:
                    dados[k] = v
                elif isinstance(v, dict) and isinstance(dados.get(k), dict):
                    for sub_k, sub_v in v.items():
                        if sub_k not in dados[k]:
                            dados[k][sub_k] = sub_v
            return dados
    except Exception as e:
        print(f"Erro ao ler {CONFIG_FILE}, usando configurações padrão: {e}")
        return CONFIG_PADRAO.copy()


def salvar_config(novas_configs: Dict[str, Any]) -> bool:
    """Salva o dicionário de configurações no arquivo config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(novas_configs, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar {CONFIG_FILE}: {e}")
        return False


def obter_pasta_raiz() -> str:
    """Retorna o caminho da pasta raiz de engenharia garantindo sua existência."""
    config = carregar_config()
    pasta = config.get("pasta_raiz", os.path.abspath("Engenharia_Projetos"))
    if not os.path.exists(pasta):
        try:
            os.makedirs(pasta, exist_ok=True)
        except Exception as e:
            print(f"Aviso: Não foi possível criar pasta raiz {pasta}: {e}")
    return pasta
