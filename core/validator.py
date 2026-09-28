"""
Módulo de Validações e Regras de Nomenclatura do Controle CAD.
Garante o formato estrito 000.000 para códigos e 000.000 - Nome para pastas.
"""

import re
from typing import Tuple, Optional

# Expressões regulares para códigos:
# Padrão para Peça e Montagem (3 dígitos, ponto, 3 dígitos)
REGEX_CODIGO_PADRAO = re.compile(r"^\d{3}\.\d{3}$")

# Padrão para Componente CO (CO seguido de hífen e 4 dígitos numéricos)
REGEX_CODIGO_CO = re.compile(r"^CO-\d{4}$", re.IGNORECASE)

# Expressão geral combinada para qualquer código aceito
REGEX_CODIGO = re.compile(r"^(\d{3}\.\d{3}|CO-\d{4})$", re.IGNORECASE)

# Expressão regular para nome de pasta no padrão (000.000 - Nome ou CO-0000 - Nome)
REGEX_PASTA = re.compile(r"^(\d{3}\.\d{3}|CO-\d{4})\s+-\s+(.+)$", re.IGNORECASE)

# Expressão para identificar pastas com 6 números juntos (ex: 123456 - Parafuso)
REGEX_PASTA_CORRIGIVEL = re.compile(r"^(\d{3})(\d{3})\s+-\s+(.+)$")

# Expressão para identificar pastas com CO sem hífen (ex: CO1234 - Rolamento)
REGEX_PASTA_CO_CORRIGIVEL = re.compile(r"^CO(\d{4})\s+-\s+(.+)$", re.IGNORECASE)

# Caracteres proibidos no sistema de arquivos Windows
CARACTERES_PROIBIDOS = set(r'<>:"/\|?*')


def validar_codigo(codigo: str, tipo: Optional[str] = None) -> Tuple[bool, str]:
    """
    Valida se o código segue rigorosamente o formato:
    - Para tipo 'CO' (Componente): CO-0000 (ex: CO-0001).
    - Para tipo 'Peça' ou 'Montagem': 000.000 (ex: 250.001).
    - Se tipo não for especificado: aceita 000.000 ou CO-0000.
    Retorna (valido, mensagem_erro).
    """
    if not codigo:
        return False, "O código não pode estar vazio."
    
    codigo_limpo = codigo.strip()

    if tipo and tipo.strip().upper() == "CO":
        if not REGEX_CODIGO_CO.match(codigo_limpo):
            return (
                False,
                f"Código '{codigo}' inválido para Componente (CO). O formato obrigatório é CO-0000 (CO seguido de hífen e 4 números). Ex: CO-0001"
            )
        return True, ""

    if tipo and tipo.strip().lower() in ("peça", "peca", "montagem"):
        if not REGEX_CODIGO_PADRAO.match(codigo_limpo):
            return (
                False,
                f"Código '{codigo}' inválido. O formato obrigatório é 000.000 (3 números, ponto, 3 números). Ex: 250.001"
            )
        return True, ""

    # Caso genérico sem tipo definido:
    if codigo_limpo.upper().startswith("CO"):
        if not REGEX_CODIGO_CO.match(codigo_limpo):
            return (
                False,
                f"Código '{codigo}' inválido para Componente (CO). O formato obrigatório é CO-0000 (ex: CO-0001)."
            )
        return True, ""

    if not REGEX_CODIGO_PADRAO.match(codigo_limpo):
        return (
            False,
            f"Código '{codigo}' inválido. O formato obrigatório é 000.000 (Ex: 250.001) ou CO-0000 para Componentes."
        )

    return True, ""


def validar_nome_peca(nome: str) -> Tuple[bool, str]:
    """
    Valida o nome/descrição da peça, garantindo caracteres válidos para o sistema de arquivos.
    """
    if not nome or not nome.strip():
        return False, "O nome da peça não pode estar vazio."
    
    nome_limpo = nome.strip()
    
    caracteres_invalidos_encontrados = [c for c in nome_limpo if c in CARACTERES_PROIBIDOS]
    if caracteres_invalidos_encontrados:
        chars = "".join(sorted(set(caracteres_invalidos_encontrados)))
        return False, f"O nome contém caracteres proibidos para arquivos Windows: {chars}"
    
    if len(nome_limpo) < 2:
        return False, "O nome da peça deve ter pelo menos 2 caracteres."
    
    return True, ""


def validar_nome_pasta(nome_pasta: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida se a pasta segue o padrão '000.000 - Nome' ou 'CO-0000 - Nome'.
    Retorna (valido, codigo_extraido, nome_extraido).
    """
    match = REGEX_PASTA.match(nome_pasta.strip())
    if match:
        codigo = match.group(1).upper()
        return True, codigo, match.group(2)
    return False, None, None


def sugerir_correcao_pasta(nome_pasta: str) -> Optional[str]:
    """
    Tenta sugerir uma correção para pastas fora do padrão:
    - '123456 - Parafuso' -> '123.456 - Parafuso'
    - 'CO1234 - Rolamento' -> 'CO-1234 - Rolamento'
    """
    match_co = REGEX_PASTA_CO_CORRIGIVEL.match(nome_pasta.strip())
    if match_co:
        num = match_co.group(1)
        nome = match_co.group(2)
        return f"CO-{num} - {nome}"

    match = REGEX_PASTA_CORRIGIVEL.match(nome_pasta.strip())
    if match:
        parte1 = match.group(1)
        parte2 = match.group(2)
        nome = match.group(3)
        return f"{parte1}.{parte2} - {nome}"
    return None


def validar_nome_arquivo_cad(nome_arquivo: str, codigo_esperado: str) -> Tuple[bool, str]:
    """
    Valida se o arquivo CAD possui exatamente o nome esperado: 000.000.ext
    Não permite sufixos de revisão (REV_A, FINAL, NOVO, etc.).
    """
    nome_upper = nome_arquivo.upper()
    extensoes_permitidas = (".SLDPRT", ".SLDASM", ".SLDDRW", ".PDF")
    
    extensao_encontrada = None
    for ext in extensoes_permitidas:
        if nome_upper.endswith(ext):
            extensao_encontrada = ext
            break
            
    if not extensao_encontrada:
        return False, f"Extensão desconhecida para arquivo de engenharia: {nome_arquivo}"
    
    nome_base = nome_arquivo[:-len(extensao_encontrada)]
    
    # Verifica variações incorretas comuns
    padroes_errados = ["_REV", "_FINAL", "_NOVO", "_V2", "_BKP", "_TESTE", "-REV"]
    for termo in padroes_errados:
        if termo in nome_base.upper():
            return False, f"Arquivo '{nome_arquivo}' contém sufixo não permitido ('{termo}'). O arquivo atual nunca deve conter revisão no nome."
    
    if nome_base != codigo_esperado:
        return False, f"Arquivo '{nome_arquivo}' possui código '{nome_base}', mas a pasta pertence ao código '{codigo_esperado}'."
    
    return True, ""


def proxima_revisao(revisao_atual: str) -> str:
    """
    Calcula a próxima letra de revisão seguindo o padrão da engenharia:
    A -> B -> C ... -> Z -> AA -> AB ...
    """
    if not revisao_atual or not revisao_atual.strip():
        return "A"
    
    rev = revisao_atual.strip().upper()
    
    # Converte letras para base 26
    num = 0
    for char in rev:
        if not ('A' <= char <= 'Z'):
            return "A"
        num = num * 26 + (ord(char) - ord('A') + 1)
    
    num += 1
    
    # Converte de volta para letras
    resultado = []
    while num > 0:
        num, resto = divmod(num - 1, 26)
        resultado.append(chr(ord('A') + resto))
        
    return "".join(reversed(resultado))
