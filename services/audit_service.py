"""
Serviço de Auditoria e Validação Geral de Projetos.
Percorre a pasta raiz de engenharia procurando:
1. Pastas fora do padrão (ex: 'Parafuso', '250001 - Eixo', 'ABC - Suporte')
2. Arquivos CAD fora do padrão (ex: '250.001_FINAL.SLDPRT', '250.001_REV_B.SLDPRT')
3. Inconsistências (pasta pertence a um código, mas o arquivo pertence a outro)
4. Estruturas incompletas (falta CAD, DESENHO, PDF ou HISTORICO)
"""

import os
from typing import List, Dict, Any, Optional
from core.models import ProblemaAuditoria
from core.validator import (
    validar_nome_pasta,
    validar_nome_arquivo_cad,
    sugerir_correcao_pasta,
    REGEX_CODIGO
)
from services.storage_service import SUBPASTAS_PADRAO


class AuditService:
    def __init__(self, pasta_raiz: str):
        self.pasta_raiz = pasta_raiz

    def executar_auditoria_completa(self) -> List[ProblemaAuditoria]:
        """Varre toda a pasta de engenharia e retorna a lista de problemas encontrados."""
        problemas: List[ProblemaAuditoria] = []
        if not os.path.exists(self.pasta_raiz):
            return [
                ProblemaAuditoria(
                    categoria="ERRO_RAIZ",
                    caminho=self.pasta_raiz,
                    descricao="A pasta raiz de engenharia não existe ou está inacessível.",
                    corrigivel=False
                )
            ]

        for item in os.scandir(self.pasta_raiz):
            if not item.is_dir():
                continue

            nome_pasta = item.name
            caminho_pasta = item.path

            # Ignora pastas temporárias do sistema ou ocultas
            if nome_pasta.startswith(".") or nome_pasta.startswith("$"):
                continue

            # 1. Validação do nome da pasta
            valido, codigo_pasta, nome_peca = validar_nome_pasta(nome_pasta)
            if not valido:
                sugestao = sugerir_correcao_pasta(nome_pasta)
                novo_caminho = None
                corrigivel = False
                if sugestao:
                    novo_caminho = os.path.join(self.pasta_raiz, sugestao)
                    corrigivel = True

                problemas.append(
                    ProblemaAuditoria(
                        categoria="PASTA_FORA_PADRAO",
                        caminho=caminho_pasta,
                        descricao=f"Pasta '{nome_pasta}' fora do padrão esperado (000.000 - Nome).",
                        sugestao=f"Renomear para '{sugestao}'" if sugestao else "Formato esperado: 000.000 - Nome da Peça",
                        corrigivel=corrigivel,
                        novo_caminho=novo_caminho
                    )
                )
                continue  # Se a pasta é inválida, segue para a próxima pasta

            # 2. Validação da estrutura interna de subpastas
            subpastas_existentes = set()
            for sub in os.scandir(caminho_pasta):
                if sub.is_dir():
                    subpastas_existentes.add(sub.name.upper())

            faltantes = [sp for sp in SUBPASTAS_PADRAO if sp not in subpastas_existentes]
            if faltantes:
                problemas.append(
                    ProblemaAuditoria(
                        categoria="ESTRUTURA_INCOMPLETA",
                        caminho=caminho_pasta,
                        descricao=f"A peça {codigo_pasta} não possui as subpastas obrigatórias: {', '.join(faltantes)}.",
                        sugestao=f"Criar as subpastas faltantes na pasta do projeto.",
                        corrigivel=True
                    )
                )

            # 3. Validação dos arquivos na pasta CAD
            pasta_cad = os.path.join(caminho_pasta, "CAD")
            if os.path.exists(pasta_cad):
                arquivos_cad = [f for f in os.listdir(pasta_cad) if not f.startswith(".")]
                if not arquivos_cad:
                    problemas.append(
                        ProblemaAuditoria(
                            categoria="ESTRUTURA_INCOMPLETA",
                            caminho=pasta_cad,
                            descricao=f"A subpasta CAD da peça {codigo_pasta} está vazia.",
                            sugestao=f"Salvar o modelo {codigo_pasta}.SLDPRT ou .SLDASM na pasta CAD.",
                            corrigivel=False
                        )
                    )
                else:
                    for arq in arquivos_cad:
                        caminho_arq = os.path.join(pasta_cad, arq)
                        if os.path.isdir(caminho_arq):
                            continue
                        val_arq, msg_arq = validar_nome_arquivo_cad(arq, codigo_pasta)
                        if not val_arq:
                            categoria_problema = "INCONSISTENCIA" if "código" in msg_arq else "ARQUIVO_FORA_PADRAO"
                            problemas.append(
                                ProblemaAuditoria(
                                    categoria=categoria_problema,
                                    caminho=caminho_arq,
                                    descricao=msg_arq,
                                    sugestao=f"O nome do arquivo deve ser rigorosamente '{codigo_pasta}.SLDPRT' ou '{codigo_pasta}.SLDASM' sem sufixos.",
                                    corrigivel=False
                                )
                            )

            # 4. Validação dos arquivos na pasta DESENHO
            pasta_desenho = os.path.join(caminho_pasta, "DESENHO")
            if os.path.exists(pasta_desenho):
                for arq in os.listdir(pasta_desenho):
                    if arq.upper().endswith(".SLDDRW"):
                        caminho_arq = os.path.join(pasta_desenho, arq)
                        val_arq, msg_arq = validar_nome_arquivo_cad(arq, codigo_pasta)
                        if not val_arq:
                            problemas.append(
                                ProblemaAuditoria(
                                    categoria="ARQUIVO_FORA_PADRAO",
                                    caminho=caminho_arq,
                                    descricao=msg_arq,
                                    sugestao=f"O desenho deve ser nomeado como '{codigo_pasta}.SLDDRW'.",
                                    corrigivel=False
                                )
                            )

            # 5. Validação dos arquivos na pasta PDF
            pasta_pdf = os.path.join(caminho_pasta, "PDF")
            if os.path.exists(pasta_pdf):
                for arq in os.listdir(pasta_pdf):
                    if arq.upper().endswith(".PDF"):
                        caminho_arq = os.path.join(pasta_pdf, arq)
                        val_arq, msg_arq = validar_nome_arquivo_cad(arq, codigo_pasta)
                        if not val_arq:
                            problemas.append(
                                ProblemaAuditoria(
                                    categoria="ARQUIVO_FORA_PADRAO",
                                    caminho=caminho_arq,
                                    descricao=msg_arq,
                                    sugestao=f"O PDF deve ser nomeado como '{codigo_pasta}.pdf'.",
                                    corrigivel=False
                                )
                            )

        return problemas

    def corrigir_pasta_automatica(self, problema: ProblemaAuditoria) -> Tuple[bool, str]:
        """Aplica a correção sugerida de renomeação de pasta com segurança."""
        if not problema.corrigivel or not problema.novo_caminho:
            return False, "Este problema não possui correção automática segura."

        if os.path.exists(problema.novo_caminho):
            return False, f"A pasta de destino '{problema.novo_caminho}' já existe!"

        try:
            os.rename(problema.caminho, problema.novo_caminho)
            return True, f"Pasta renomeada com sucesso para '{os.path.basename(problema.novo_caminho)}'."
        except Exception as e:
            return False, f"Erro ao renomear pasta: {e}"

    def criar_subpastas_faltantes(self, pasta_caminho: str) -> Tuple[bool, str]:
        """Cria as subpastas padrão ausentes em uma pasta de peça."""
        try:
            for sub in SUBPASTAS_PADRAO:
                caminho_sub = os.path.join(pasta_caminho, sub)
                os.makedirs(caminho_sub, exist_ok=True)
            return True, "Subpastas criadas com sucesso."
        except Exception as e:
            return False, f"Erro ao criar subpastas: {e}"
