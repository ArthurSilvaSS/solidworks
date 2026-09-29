"""
Serviço de Armazenamento do Controle CAD.
Responsável por criar a estrutura de pastas, ler e salvar controle.json,
e localizar arquivos CAD, desenhos e PDFs.
"""

import os
import re
import json
import shutil
import datetime
from typing import Tuple, List, Optional, Dict, Any
from core.models import PecaInfo, HistoricoEntrada, ComponenteItem, obter_usuario_atual, LINHAS_PRODUTO
from core.validator import (
    validar_nome_pasta,
    validar_codigo,
    validar_nome_peca,
    REGEX_CODIGO,
    REGEX_CODIGO_PADRAO,
    REGEX_CODIGO_CO,
    sugerir_correcao_pasta
)
from core.logger import registrar_log

SUBPASTAS_PADRAO = ["CAD", "DESENHO", "PDF", "HISTORICO"]
ARQUIVO_CONTROLE = "controle.json"
ARQUIVO_KITS = "kits.json"


class StorageService:
    def __init__(self, pasta_raiz: str):
        self.pasta_raiz = pasta_raiz
        os.makedirs(self.pasta_raiz, exist_ok=True)

    def obter_pasta_peca(self, codigo: str, nome: str) -> str:
        """Gera o caminho absoluto da pasta da peça no padrão '000.000 - Nome'."""
        nome_pasta = f"{codigo} - {nome.strip()}"
        return os.path.join(self.pasta_raiz, nome_pasta)

    def criar_estrutura_peca(self, peca: PecaInfo) -> Tuple[bool, str]:
        """
        Cria a estrutura de pastas padronizada:
        000.000 - Nome da Peça/
        ├── CAD
        ├── DESENHO
        ├── PDF
        ├── HISTORICO
        └── controle.json
        """
        # Validação prévia
        if peca.tipo and peca.tipo.strip().upper() == "CO":
            peca.codigo = peca.codigo.strip().upper()

        val_cod, msg_cod = validar_codigo(peca.codigo, peca.tipo)
        if not val_cod:
            return False, msg_cod

        val_nome, msg_nome = validar_nome_peca(peca.nome)
        if not val_nome:
            return False, msg_nome

        pasta_destino = self.obter_pasta_peca(peca.codigo, peca.nome)
        
        if os.path.exists(pasta_destino):
            return False, f"A pasta da peça já existe em: {pasta_destino}"

        try:
            os.makedirs(pasta_destino, exist_ok=False)
            
            # Cria subpastas obrigatórias
            for sub in SUBPASTAS_PADRAO:
                os.makedirs(os.path.join(pasta_destino, sub), exist_ok=True)

            # Define histórico inicial caso não exista
            if not peca.historico:
                peca.historico = [
                    HistoricoEntrada(
                        revisao=peca.revisao_atual,
                        data=peca.criado_em,
                        usuario=peca.criado_por,
                        motivo="Criação inicial do projeto"
                    )
                ]

            peca.pasta_path = pasta_destino
            self.salvar_controle_json(peca)

            # Registra kits automaticamente com a linha de produto da peça
            if peca.kits:
                p_linha = getattr(peca, "linha_produto", "MedicalFix") or "MedicalFix"
                for k in peca.kits:
                    self.cadastrar_kit(k, linha=p_linha)

            registrar_log(
                "PROJETO CRIADO",
                {
                    "Código": peca.codigo,
                    "Nome": peca.nome,
                    "Tipo": peca.tipo,
                    "Revisão": peca.revisao_atual,
                    "Usuário": peca.criado_por,
                    "Caminho": pasta_destino
                }
            )

            return True, pasta_destino
        except Exception as e:
            registrar_log("ERRO CRIAR ESTRUTURA", {"Código": peca.codigo, "Erro": str(e)}, nivel="ERROR")
            return False, f"Erro ao criar estrutura de pastas: {e}"

    def salvar_controle_json(self, peca: PecaInfo) -> bool:
        """Salva os metadados da peça no arquivo controle.json da pasta."""
        if not peca.pasta_path:
            peca.pasta_path = self.obter_pasta_peca(peca.codigo, peca.nome)
            
        caminho_json = os.path.join(peca.pasta_path, ARQUIVO_CONTROLE)
        try:
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(peca.to_dict(), f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            registrar_log("ERRO SALVAR CONTROLE.JSON", {"Caminho": caminho_json, "Erro": str(e)}, nivel="ERROR")
            return False

    def carregar_peca_por_pasta(self, pasta_caminho: str) -> Optional[PecaInfo]:
        """Carrega os dados da peça a partir do controle.json ou pelo nome da pasta."""
        if not os.path.isdir(pasta_caminho):
            return None

        caminho_json = os.path.join(pasta_caminho, ARQUIVO_CONTROLE)
        if os.path.exists(caminho_json):
            try:
                with open(caminho_json, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    return PecaInfo.from_dict(dados, pasta_path=pasta_caminho)
            except Exception as e:
                registrar_log("ERRO LER CONTROLE.JSON", {"Caminho": caminho_json, "Erro": str(e)}, nivel="WARNING")

        # Fallback: tentar reconstruir a partir do nome da pasta
        nome_pasta = os.path.basename(pasta_caminho)
        valido, cod, nome = validar_nome_pasta(nome_pasta)
        if valido and cod and nome:
            # Detecta tipo verificando se é CO ou analisando extensão no CAD
            pasta_cad = os.path.join(pasta_caminho, "CAD")
            if cod.upper().startswith("CO-"):
                tipo = "CO"
            else:
                tipo = "Peça"
                if os.path.exists(pasta_cad):
                    for f in os.listdir(pasta_cad):
                        if f.upper().endswith(".SLDASM"):
                            tipo = "Montagem"
                            break
            
            peca = PecaInfo(
                codigo=cod,
                nome=nome,
                descricao=nome,
                tipo=tipo,
                revisao_atual="A",
                criado_por="Importado",
                pasta_path=pasta_caminho,
                historico=[
                    HistoricoEntrada(revisao="A", data="Desconhecida", usuario="Sistema", motivo="Recuperado da pasta")
                ]
            )
            # Salva o controle.json gerado para consistência futura
            self.salvar_controle_json(peca)
            return peca

        return None

    def listar_todas_pecas(self) -> List[PecaInfo]:
        """Varre a pasta raiz e retorna todas as peças identificadas."""
        pecas: List[PecaInfo] = []
        if not os.path.exists(self.pasta_raiz):
            return pecas

        for entrada in os.scandir(self.pasta_raiz):
            if entrada.is_dir():
                peca = self.carregar_peca_por_pasta(entrada.path)
                if peca:
                    pecas.append(peca)
        
        # Ordena por código
        pecas.sort(key=lambda p: p.codigo)
        return pecas

    def obter_caminho_cad(self, peca: PecaInfo) -> Optional[str]:
        """Localiza o arquivo CAD ativo (.SLDPRT ou .SLDASM)."""
        pasta_cad = os.path.join(peca.pasta_path, "CAD")
        if not os.path.exists(pasta_cad):
            return None
        
        ext = ".SLDASM" if peca.tipo == "Montagem" else ".SLDPRT"
        caminho_padrao = os.path.join(pasta_cad, f"{peca.codigo}{ext}")
        if os.path.exists(caminho_padrao):
            return caminho_padrao
        
        # Procura por qualquer .SLDPRT ou .SLDASM correspondente ao código
        for arq in os.listdir(pasta_cad):
            if arq.upper().startswith(peca.codigo.upper()) and (arq.upper().endswith(".SLDPRT") or arq.upper().endswith(".SLDASM")):
                return os.path.join(pasta_cad, arq)
        return None

    def obter_caminho_desenho(self, peca: PecaInfo) -> Optional[str]:
        """Localiza o arquivo de desenho ativo (.SLDDRW)."""
        pasta_desenho = os.path.join(peca.pasta_path, "DESENHO")
        if not os.path.exists(pasta_desenho):
            return None
        caminho_esperado = os.path.join(pasta_desenho, f"{peca.codigo}.SLDDRW")
        if os.path.exists(caminho_esperado):
            return caminho_esperado
        for arq in os.listdir(pasta_desenho):
            if arq.upper().endswith(".SLDDRW"):
                return os.path.join(pasta_desenho, arq)
        return None

    def obter_caminho_pdf(self, peca: PecaInfo) -> Optional[str]:
        """Localiza o arquivo PDF ativo (.pdf)."""
        pasta_pdf = os.path.join(peca.pasta_path, "PDF")
        if not os.path.exists(pasta_pdf):
            return None
        caminho_esperado = os.path.join(pasta_pdf, f"{peca.codigo}.pdf")
        if os.path.exists(caminho_esperado):
            return caminho_esperado
        for arq in os.listdir(pasta_pdf):
            if arq.upper().endswith(".PDF"):
                return os.path.join(pasta_pdf, arq)
        return None

    def peca_tem_cad(self, peca: PecaInfo) -> bool:
        """Verifica se a peça possui o arquivo CAD (.SLDPRT ou .SLDASM)."""
        caminho = self.obter_caminho_cad(peca)
        return bool(caminho and os.path.exists(caminho))

    def peca_tem_desenho(self, peca: PecaInfo) -> bool:
        """Verifica se a peça possui o desenho técnico 2D (.SLDDRW)."""
        caminho = self.obter_caminho_desenho(peca)
        return bool(caminho and os.path.exists(caminho))

    def peca_tem_pdf(self, peca: PecaInfo) -> bool:
        """Verifica se a peça possui o arquivo PDF exportado (.pdf)."""
        caminho = self.obter_caminho_pdf(peca)
        return bool(caminho and os.path.exists(caminho))

    def peca_precisa_gerar_pdf(self, peca: PecaInfo) -> Tuple[bool, str]:
        """
        Verifica se um projeto já tem o modelo CAD e o desenho 2D (.SLDDRW),
        e se o PDF correspondente precisa ser gerado automaticamente.
        
        Retorna (precisa_gerar, motivo).
        """
        if not self.peca_tem_cad(peca):
            return False, "Peça não possui modelo 3D CAD."

        caminho_des = self.obter_caminho_desenho(peca)
        if not caminho_des or not os.path.exists(caminho_des):
            return False, "Peça não possui folha de desenho 2D (.SLDDRW)."

        caminho_pdf = self.obter_caminho_pdf(peca)
        if not caminho_pdf or not os.path.exists(caminho_pdf):
            return True, "PDF ainda não foi gerado."

        # Se o arquivo .SLDDRW foi modificado após a exportação do PDF, está desatualizado
        try:
            mtime_des = os.path.getmtime(caminho_des)
            mtime_pdf = os.path.getmtime(caminho_pdf)
            if mtime_des > mtime_pdf:
                return True, "Desenho 2D foi alterado após o último PDF (necessário atualizar)."
        except Exception:
            pass

        return False, "PDF já está atualizado."


    def excluir_peca(self, peca: PecaInfo, sw_client=None) -> Tuple[bool, str]:
        """
        Exclui permanentemente o desenho/peça selecionado e todas as suas pastas
        (CAD, DESENHO, PDF, HISTORICO) além de arquivos de metadados (controle.json, preview.png).
        
        Conta com proteções estritas de segurança para garantir que apenas a pasta
        específica do projeto dentro da pasta raiz seja apagada.
        """
        if not peca:
            return False, "Nenhum desenho foi selecionado para exclusão."

        pasta_alvo = peca.pasta_path or self.obter_pasta_peca(peca.codigo, peca.nome)
        if not pasta_alvo or not os.path.exists(pasta_alvo):
            return False, f"A pasta do desenho '{peca.codigo}' não existe ou já foi removida."

        pasta_alvo_abs = os.path.abspath(pasta_alvo)
        pasta_raiz_abs = os.path.abspath(self.pasta_raiz)

        # Trava 1: Nunca permitir apagar a pasta raiz
        if pasta_alvo_abs == pasta_raiz_abs:
            registrar_log("BLOQUEIO EXCLUSAO", {"Motivo": "Tentativa de excluir pasta raiz", "Alvo": pasta_alvo_abs}, nivel="ERROR")
            return False, "Operação bloqueada: não é permitido excluir a pasta raiz de engenharia."

        # Trava 2: Certifica-se de que a pasta alvo é estritamente uma subpasta de pasta_raiz
        rel_caminho = os.path.relpath(pasta_alvo_abs, pasta_raiz_abs)
        if rel_caminho.startswith("..") or rel_caminho == ".":
            registrar_log("BLOQUEIO EXCLUSAO", {"Motivo": "Pasta fora da raiz", "Alvo": pasta_alvo_abs}, nivel="ERROR")
            return False, "Operação bloqueada: o caminho informado está fora da pasta raiz de engenharia."

        # Trava 3: Se houver SolidWorks aberto, fecha os arquivos da pasta para liberar locks do Windows
        if sw_client:
            try:
                if hasattr(sw_client, "fechar_documentos_da_pasta"):
                    sw_client.fechar_documentos_da_pasta(pasta_alvo_abs)
                else:
                    cad_arq = self.obter_caminho_cad(peca)
                    des_arq = self.obter_caminho_desenho(peca)
                    if cad_arq and hasattr(sw_client, "fechar_documento"):
                        sw_client.fechar_documento(cad_arq)
                    if des_arq and hasattr(sw_client, "fechar_documento"):
                        sw_client.fechar_documento(des_arq)
            except Exception as e:
                registrar_log("AVISO FECHAR DOCS SW", {"Erro": str(e)}, nivel="WARNING")

        # Função auxiliar para remover atributo somente-leitura se necessário (comum no Windows)
        def _limpar_somente_leitura(func, path, exc_info):
            import stat
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            import sys
            if sys.version_info >= (3, 12):
                def _on_exc(func, path, exc):
                    import stat
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(pasta_alvo_abs, onexc=_on_exc)
            else:
                shutil.rmtree(pasta_alvo_abs, onerror=_limpar_somente_leitura)

            # Verifica se a pasta foi completamente removida
            if os.path.exists(pasta_alvo_abs):
                return False, (
                    f"A pasta '{os.path.basename(pasta_alvo_abs)}' não pôde ser completamente excluída.\n\n"
                    "Verifique se algum arquivo ou desenho está aberto no SolidWorks, leitor de PDF ou Windows Explorer."
                )

            # Registra auditoria da exclusão
            registrar_log(
                "DESENHO EXCLUÍDO",
                {
                    "Código": peca.codigo,
                    "Nome": peca.nome,
                    "Tipo": peca.tipo,
                    "Revisão": peca.revisao_atual,
                    "Usuário": obter_usuario_atual(),
                    "Pasta Excluída": pasta_alvo_abs,
                    "Estrutura Removida": "CAD, DESENHO, PDF, HISTORICO e controle.json"
                },
                nivel="INFO"
            )

            return True, f"O desenho '{peca.codigo} - {peca.nome}' e todas as suas pastas foram excluídos com sucesso."

        except PermissionError as pe:
            registrar_log("ERRO PERMISSAO EXCLUSAO", {"Alvo": pasta_alvo_abs, "Erro": str(pe)}, nivel="ERROR")
            return False, (
                f"Permissão negada ao tentar excluir as pastas do projeto:\n{pasta_alvo_abs}\n\n"
                "Um ou mais arquivos estão em uso. Feche o SolidWorks ou outros aplicativos e tente novamente."
            )
        except Exception as e:
            registrar_log("ERRO EXCLUIR PASTA", {"Alvo": pasta_alvo_abs, "Erro": str(e)}, nivel="ERROR")
            return False, f"Ocorreu um erro ao excluir as pastas do desenho:\n{e}"

    def obter_todos_cos(self) -> List[PecaInfo]:
        """Retorna todas as peças cadastradas do tipo CO (Componentes)."""
        todas = self.listar_todas_pecas()
        return [p for p in todas if p.tipo.upper() == "CO"]

    def obter_caminho_cad_por_codigo(self, codigo: str) -> Optional[str]:
        """Localiza o caminho do arquivo CAD (.SLDPRT ou .SLDASM) para um código específico."""
        cod_limpo = codigo.strip().upper()
        todas = self.listar_todas_pecas()
        for p in todas:
            if p.codigo.upper() == cod_limpo:
                return self.obter_caminho_cad(p)
        return None

    # ------------------ CATÁLOGO E GERENCIAMENTO DE KITS ------------------

    def _caminho_kits_json(self) -> str:
        """Caminho absoluto do arquivo kits.json na raiz de projetos."""
        return os.path.join(self.pasta_raiz, ARQUIVO_KITS)

    def obter_catalogo_kits(self, linha: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna o catálogo completo de kits cadastrados no arquivo kits.json,
        opcionalmente filtrado pela linha de produto informada.
        Sincroniza automaticamente quaisquer kits pré-existentes nas peças cadastradas.
        """
        catalogo: List[Dict[str, Any]] = []
        caminho = self._caminho_kits_json()

        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    if isinstance(dados, list):
                        catalogo = dados
            except Exception as e:
                registrar_log("ERRO LEITURA KITS", {"Arquivo": caminho, "Erro": str(e)})

        # Sincroniza kits que existam nas peças mas ainda não estejam em kits.json
        nomes_no_catalogo = {k.get("nome", "").lower(): k for k in catalogo if k.get("nome")}
        modificado = False

        for p in self.listar_todas_pecas():
            linha_da_peca = getattr(p, "linha_produto", "MedicalFix") or "MedicalFix"
            for kit_nome in p.kits:
                k_clean = kit_nome.strip()
                if k_clean and k_clean.lower() not in nomes_no_catalogo:
                    novo_kit = {
                        "nome": k_clean,
                        "descricao": "",
                        "linha": linha_da_peca,
                        "criado_em": p.criado_em or datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    }
                    catalogo.append(novo_kit)
                    nomes_no_catalogo[k_clean.lower()] = novo_kit
                    modificado = True

        if modificado:
            self.salvar_catalogo_kits(catalogo)

        # Se houver filtro de linha específico
        if linha and linha.strip() and linha.strip() != "Todas as Linhas":
            linha_alvo = linha.strip().lower()
            catalogo = [
                k for k in catalogo
                if k.get("linha", "").lower() == linha_alvo or k.get("linha", "") in ("Todas as Linhas", "Todas", "Geral", "")
            ]

        return sorted(catalogo, key=lambda x: x.get("nome", "").lower())

    def salvar_catalogo_kits(self, kits: List[Dict[str, Any]]) -> bool:
        """Persiste a lista de kits no arquivo kits.json."""
        caminho = self._caminho_kits_json()
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(kits, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            registrar_log("ERRO SALVAR KITS", {"Arquivo": caminho, "Erro": str(e)})
            return False

    def cadastrar_kit(self, nome: str, descricao: str = "", linha: Optional[str] = "MedicalFix") -> Tuple[bool, str]:
        """Cadastra um novo kit no sistema garantindo nome único e associando à sua linha de produto."""
        nome = nome.strip()
        if not nome:
            return False, "O nome do kit não pode ser vazio."

        catalogo = self.obter_catalogo_kits()
        for item in catalogo:
            if item.get("nome", "").lower() == nome.lower():
                return False, f"Já existe um kit cadastrado com o nome '{item.get('nome')}'."

        linha_final = linha.strip() if linha is not None else "MedicalFix"
        if not linha_final or linha_final in ("Todas as Linhas", "Todas", "Geral"):
            linha_final = "Todas as Linhas"

        novo_item = {
            "nome": nome,
            "descricao": descricao.strip(),
            "linha": linha_final,
            "criado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        catalogo.append(novo_item)

        if not self.salvar_catalogo_kits(catalogo):
            return False, "Erro ao gravar dados no arquivo kits.json."

        registrar_log("KIT CADASTRADO", {"Nome": nome, "Descrição": descricao, "Linha": novo_item["linha"]})
        return True, f"Kit '{nome}' cadastrado com sucesso na linha '{novo_item['linha']}'!"

    def editar_kit(self, nome_antigo: str, nome_novo: str, descricao_nova: str = "", linha_nova: str = "") -> Tuple[bool, str]:
        """Atualiza nome, descrição e linha de produto de um kit existente."""
        nome_antigo = nome_antigo.strip()
        nome_novo = nome_novo.strip() or nome_antigo

        if nome_antigo.lower() != nome_novo.lower():
            ok_ren, msg_ren = self.renomear_kit(nome_antigo, nome_novo)
            if not ok_ren:
                return False, msg_ren
            nome_alvo = nome_novo
        else:
            nome_alvo = nome_antigo

        catalogo = self.obter_catalogo_kits()
        for item in catalogo:
            if item.get("nome", "").lower() == nome_alvo.lower():
                if descricao_nova is not None and descricao_nova != "":
                    item["descricao"] = descricao_nova.strip()
                if linha_nova:
                    item["linha"] = linha_nova.strip()
                break

        self.salvar_catalogo_kits(catalogo)
        return True, f"Kit '{nome_alvo}' atualizado com sucesso."

    def renomear_kit(self, nome_antigo: str, nome_novo: str) -> Tuple[bool, str]:
        """Renomeia um kit existente no catálogo e atualiza todas as peças que o utilizam."""
        nome_antigo = nome_antigo.strip()
        nome_novo = nome_novo.strip()

        if not nome_novo:
            return False, "O novo nome do kit não pode ser vazio."
        if nome_antigo.lower() == nome_novo.lower():
            return False, "O novo nome é idêntico ao atual."

        catalogo = self.obter_catalogo_kits()
        for item in catalogo:
            if item.get("nome", "").lower() == nome_novo.lower() and item.get("nome", "").lower() != nome_antigo.lower():
                return False, f"Já existe outro kit com o nome '{item.get('nome')}'."

        achou = False
        for item in catalogo:
            if item.get("nome", "").lower() == nome_antigo.lower():
                item["nome"] = nome_novo
                achou = True
                break

        if not achou:
            catalogo.append({
                "nome": nome_novo,
                "descricao": "",
                "criado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            })

        self.salvar_catalogo_kits(catalogo)

        # Atualiza o nome nas peças vinculadas
        total_atualizadas = 0
        for p in self.listar_todas_pecas():
            modificado = False
            novos_kits = []
            for k in p.kits:
                if k.lower() == nome_antigo.lower():
                    novos_kits.append(nome_novo)
                    modificado = True
                else:
                    novos_kits.append(k)
            if modificado:
                p.kits = novos_kits
                self.salvar_controle_json(p)
                total_atualizadas += 1

        registrar_log(
            "KIT RENOMEADO",
            {"De": nome_antigo, "Para": nome_novo, "Peças Atualizadas": total_atualizadas}
        )
        return True, f"Kit renomeado para '{nome_novo}' ({total_atualizadas} peças atualizadas)."

    def excluir_kit(self, nome: str, desvincular_pecas: bool = True) -> Tuple[bool, str]:
        """Exclui um kit do catálogo e opcionalmente desvincula de todas as peças associadas."""
        nome = nome.strip()
        catalogo = self.obter_catalogo_kits()
        novo_catalogo = [k for k in catalogo if k.get("nome", "").lower() != nome.lower()]
        self.salvar_catalogo_kits(novo_catalogo)

        total_desvinculadas = 0
        if desvincular_pecas:
            for p in self.listar_todas_pecas():
                if any(k.lower() == nome.lower() for k in p.kits):
                    p.kits = [k for k in p.kits if k.lower() != nome.lower()]
                    self.salvar_controle_json(p)
                    total_desvinculadas += 1

        registrar_log(
            "KIT EXCLUÍDO",
            {"Nome": nome, "Peças Desvinculadas": total_desvinculadas}
        )
        return True, f"Kit '{nome}' excluído com sucesso ({total_desvinculadas} peças desvinculadas)."

    def obter_pecas_do_kit(self, nome_kit: str) -> List[PecaInfo]:
        """Retorna todas as peças e montagens que fazem parte de um determinado kit."""
        alvo = nome_kit.strip().lower()
        return [p for p in self.listar_todas_pecas() if any(k.lower() == alvo for k in p.kits)]

    def vincular_peca_a_kit(self, codigo_peca: str, nome_kit: str) -> bool:
        """Adiciona um kit à lista de kits de uma peça específica."""
        nome_kit = nome_kit.strip()
        cod_limpo = codigo_peca.strip().upper()
        for p in self.listar_todas_pecas():
            if p.codigo.upper() == cod_limpo:
                if not any(k.lower() == nome_kit.lower() for k in p.kits):
                    p.kits.append(nome_kit)
                    return self.salvar_controle_json(p)
                return True
        return False

    def desvincular_peca_de_kit(self, codigo_peca: str, nome_kit: str) -> bool:
        """Remove o kit da lista de kits de uma peça específica."""
        alvo = nome_kit.strip().lower()
        cod_limpo = codigo_peca.strip().upper()
        for p in self.listar_todas_pecas():
            if p.codigo.upper() == cod_limpo:
                if any(k.lower() == alvo for k in p.kits):
                    p.kits = [k for k in p.kits if k.lower() != alvo]
                    return self.salvar_controle_json(p)
                return True
        return False

    def obter_todos_kits(self, linha: Optional[str] = None) -> List[str]:
        """
        Retorna a lista de nomes de kits únicos cadastrados no sistema,
        opcionalmente filtrados pela linha de produto informada.
        """
        kits_unicos = set()
        catalogo = self.obter_catalogo_kits(linha=linha)
        for item in catalogo:
            k_nome = item.get("nome", "").strip()
            if k_nome:
                kits_unicos.add(k_nome)

        for p in self.listar_todas_pecas():
            if linha and linha.strip() and linha.strip() != "Todas as Linhas":
                p_linha = getattr(p, "linha_produto", "MedicalFix") or "MedicalFix"
                if p_linha.lower() != linha.strip().lower():
                    continue
            for k in p.kits:
                k_clean = k.strip()
                if k_clean:
                    kits_unicos.add(k_clean)
        return sorted(kits_unicos, key=lambda s: s.lower())

    @staticmethod
    def extrair_dados_de_arquivo(caminho_ou_nome: str) -> Tuple[Optional[str], str, str]:
        """
        Analisa o nome de um arquivo (ex: '250.001 - Suporte Motor.SLDPRT', 'CO-0001 - Anel.SLDPRT',
        '100.001 - Montagem Base.SLDASM' ou 'Suporte.SLDPRT') e extrai:
        (codigo_sugerido, nome_sugerido, tipo_sugerido)
        """
        nome_arquivo = os.path.basename(caminho_ou_nome)
        ext = os.path.splitext(nome_arquivo)[1].upper()
        stem = os.path.splitext(nome_arquivo)[0].strip()

        # Determina tipo baseado na extensão ou prefixo
        if ext == ".SLDASM":
            tipo_sugerido = "Montagem"
        elif stem.upper().startswith("CO-") or stem.upper().startswith("CO"):
            tipo_sugerido = "CO"
        else:
            tipo_sugerido = "Peça"

        # 1. Padrão estrito: 000.000 - Nome ou CO-0000 - Nome
        m_padrao = re.match(r"^(\d{3}\.\d{3}|CO-\d{4})\s*[-_]\s*(.+)$", stem, re.IGNORECASE)
        if m_padrao:
            cod = m_padrao.group(1).upper()
            nome = m_padrao.group(2).strip()
            if cod.startswith("CO-"):
                tipo_sugerido = "CO"
            return cod, nome, tipo_sugerido

        # 2. Padrão sem nome (apenas o código no arquivo, ex: 250.001.SLDPRT ou CO-0001.SLDPRT)
        m_apenas_cod = re.match(r"^(\d{3}\.\d{3}|CO-\d{4})$", stem, re.IGNORECASE)
        if m_apenas_cod:
            cod = m_apenas_cod.group(1).upper()
            if cod.startswith("CO-"):
                tipo_sugerido = "CO"
            return cod, cod, tipo_sugerido

        # 3. Padrão corrigível: 123456 - Nome -> 123.456 - Nome
        m_6dig = re.match(r"^(\d{3})(\d{3})\s*[-_]\s*(.+)$", stem)
        if m_6dig:
            cod = f"{m_6dig.group(1)}.{m_6dig.group(2)}"
            nome = m_6dig.group(3).strip()
            return cod, nome, tipo_sugerido

        # 4. Padrão corrigível CO: CO0001 - Nome -> CO-0001 - Nome
        m_co_corr = re.match(r"^CO(\d{4})\s*[-_]\s*(.+)$", stem, re.IGNORECASE)
        if m_co_corr:
            cod = f"CO-{m_co_corr.group(1)}"
            nome = m_co_corr.group(2).strip()
            return cod, nome, "CO"

        # 5. Padrão apenas números 6 dígitos: 123456 -> 123.456
        m_so_6dig = re.match(r"^(\d{3})(\d{3})$", stem)
        if m_so_6dig:
            cod = f"{m_so_6dig.group(1)}.{m_so_6dig.group(2)}"
            return cod, cod, tipo_sugerido

        # 6. Não possui código detectável no nome do arquivo
        return None, stem, tipo_sugerido

    def importar_peca_existente(
        self,
        caminho_3d: Optional[str] = None,
        caminho_2d: Optional[str] = None,
        caminho_pdf: Optional[str] = None,
        codigo: str = "",
        nome: str = "",
        tipo: str = "Peça",
        descricao: str = "",
        revisao: str = "A",
        kits: Optional[List[str]] = None,
        componentes: Optional[List[ComponenteItem]] = None,
        copiar: bool = True,
        linha_produto: str = "MedicalFix"
    ) -> Tuple[bool, Optional[PecaInfo], str]:
        """
        Importa uma peça ou montagem pronta (3D e/ou 2D) para o sistema,
        criando a estrutura padrão de pastas (CAD, DESENHO, PDF, HISTORICO)
        e o arquivo controle.json com todos os metadados.
        
        Suporta copiar (preservando o original) ou mover os arquivos.
        """
        # 1. Validação de arquivos fornecidos
        tem_3d = bool(caminho_3d and os.path.exists(caminho_3d))
        tem_2d = bool(caminho_2d and os.path.exists(caminho_2d))

        if not tem_3d and not tem_2d:
            return False, None, "Nenhum arquivo 3D (.SLDPRT/.SLDASM) ou 2D (.SLDDRW) válido foi encontrado para importação."

        # Se caminho 3D for montagem (.SLDASM), assegura tipo Montagem
        if tem_3d and caminho_3d.upper().endswith(".SLDASM"):
            tipo = "Montagem"

        if tipo.upper() == "CO":
            codigo = codigo.strip().upper()
        else:
            codigo = codigo.strip()

        # 2. Validação estrita do código
        val_cod, msg_cod = validar_codigo(codigo, tipo=tipo)
        if not val_cod:
            return False, None, msg_cod

        # 3. Validação do nome
        nome = nome.strip()
        val_nome, msg_nome = validar_nome_peca(nome)
        if not val_nome:
            return False, None, msg_nome

        # 4. Verificação de duplicidade de pasta e de código
        pasta_destino = self.obter_pasta_peca(codigo, nome)
        if os.path.exists(pasta_destino):
            return False, None, f"A pasta da peça já existe em: {os.path.basename(pasta_destino)}"

        for p in self.listar_todas_pecas():
            if p.codigo.upper() == codigo.upper():
                return False, None, f"O código '{codigo}' já está cadastrado para a peça '{p.nome}'."

        try:
            # 5. Criação das pastas padronizadas
            os.makedirs(pasta_destino, exist_ok=False)
            for sub in SUBPASTAS_PADRAO:
                os.makedirs(os.path.join(pasta_destino, sub), exist_ok=True)

            # 6. Cópia ou Movimentação do arquivo 3D
            if tem_3d:
                ext_3d = ".SLDASM" if tipo == "Montagem" else ".SLDPRT"
                dest_3d = os.path.join(pasta_destino, "CAD", f"{codigo}{ext_3d}")
                if copiar:
                    shutil.copy2(caminho_3d, dest_3d)
                else:
                    shutil.move(caminho_3d, dest_3d)

            # 7. Cópia ou Movimentação do arquivo 2D
            if tem_2d:
                dest_2d = os.path.join(pasta_destino, "DESENHO", f"{codigo}.SLDDRW")
                if copiar:
                    shutil.copy2(caminho_2d, dest_2d)
                else:
                    shutil.move(caminho_2d, dest_2d)

            # 8. Cópia ou Movimentação do PDF (se fornecido)
            if caminho_pdf and os.path.exists(caminho_pdf):
                dest_pdf = os.path.join(pasta_destino, "PDF", f"{codigo}.pdf")
                if copiar:
                    shutil.copy2(caminho_pdf, dest_pdf)
                else:
                    shutil.move(caminho_pdf, dest_pdf)

            # 9. Criação do PecaInfo e controle.json
            nova_peca = PecaInfo(
                codigo=codigo,
                nome=nome,
                descricao=descricao or nome,
                tipo=tipo,
                revisao_atual=revisao or "A",
                pasta_path=pasta_destino,
                criado_por=obter_usuario_atual(),
                criado_em=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                kits=kits or [],
                componentes=componentes or [],
                linha_produto=linha_produto or "MedicalFix",
                historico=[
                    HistoricoEntrada(
                        revisao=revisao or "A",
                        data=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        usuario=obter_usuario_atual(),
                        motivo="Importação de desenho pronto (3D/2D)"
                    )
                ]
            )
            self.salvar_controle_json(nova_peca)

            # 10. Atualiza catálogo de kits se necessário
            if kits:
                for k in kits:
                    self.cadastrar_kit(k, linha=linha_produto)

            # 11. Log de auditoria
            registrar_log(
                "PEÇA IMPORTADA",
                {
                    "Código": codigo,
                    "Nome": nome,
                    "Tipo": tipo,
                    "Linha": linha_produto,
                    "Revisão": revisao,
                    "Pasta": pasta_destino,
                    "Arquivo 3D": os.path.basename(caminho_3d) if caminho_3d else None,
                    "Arquivo 2D": os.path.basename(caminho_2d) if caminho_2d else None,
                    "Ação": "Cópia" if copiar else "Movimentação"
                },
                nivel="INFO"
            )

            return True, nova_peca, f"Peça '{codigo} - {nome}' importada com sucesso para o sistema!"
        except Exception as e:
            # Em caso de falha durante a cópia, remove a pasta criada
            if os.path.exists(pasta_destino):
                try:
                    shutil.rmtree(pasta_destino, ignore_errors=True)
                except Exception:
                    pass
            registrar_log("ERRO IMPORTAR PECA", {"Código": codigo, "Erro": str(e)}, nivel="ERROR")
            return False, None, f"Erro ao importar arquivos da peça: {e}"

    def escanear_pasta_externa(self, caminho_pasta: str, recursivo: bool = True) -> List[Dict[str, Any]]:
        """
        Varre uma pasta externa em busca de arquivos do SolidWorks (.SLDPRT, .SLDASM, .SLDDRW, .PDF),
        agrupando arquivos 3D e 2D correspondentes e sugerindo código, nome e tipo.
        """
        itens_detectados: List[Dict[str, Any]] = []
        if not os.path.exists(caminho_pasta) or not os.path.isdir(caminho_pasta):
            return itens_detectados

        # Lista de peças cadastradas atualmente no sistema para checar duplicidades
        pecas_cadastradas = {p.codigo.upper(): p for p in self.listar_todas_pecas()}

        # 1. Coleta todos os arquivos relevantes
        arquivos_3d = []
        arquivos_2d = []
        arquivos_pdf = []

        if recursivo:
            for raiz, _, files in os.walk(caminho_pasta):
                u_raiz = raiz.upper()
                if "HISTORICO" in u_raiz or "$RECYCLE.BIN" in u_raiz or ".GIT" in u_raiz:
                    continue
                for f in files:
                    full = os.path.join(raiz, f)
                    u = f.upper()
                    if u.endswith(".SLDPRT") or u.endswith(".SLDASM"):
                        arquivos_3d.append(full)
                    elif u.endswith(".SLDDRW"):
                        arquivos_2d.append(full)
                    elif u.endswith(".PDF"):
                        arquivos_pdf.append(full)
        else:
            for entrada in os.scandir(caminho_pasta):
                if entrada.is_file():
                    u = entrada.name.upper()
                    if u.endswith(".SLDPRT") or u.endswith(".SLDASM"):
                        arquivos_3d.append(entrada.path)
                    elif u.endswith(".SLDDRW"):
                        arquivos_2d.append(entrada.path)
                    elif u.endswith(".PDF"):
                        arquivos_pdf.append(entrada.path)

        # Mapa de 2D e PDF por nome base (sem extensão)
        mapa_2d: Dict[str, List[str]] = {}
        for p2d in arquivos_2d:
            stem = os.path.splitext(os.path.basename(p2d))[0].upper()
            mapa_2d.setdefault(stem, []).append(p2d)

        mapa_pdf: Dict[str, List[str]] = {}
        for ppdf in arquivos_pdf:
            stem = os.path.splitext(os.path.basename(ppdf))[0].upper()
            mapa_pdf.setdefault(stem, []).append(ppdf)

        pares_2d_utilizados = set()
        pares_pdf_utilizados = set()

        id_counter = 1

        # 2. Pareia a partir de cada arquivo 3D
        for p3d in arquivos_3d:
            stem_3d = os.path.splitext(os.path.basename(p3d))[0].strip()
            stem_upper = stem_3d.upper()
            dir_3d = os.path.dirname(p3d)

            # Localiza 2D correspondente
            p2d_encontrado = None
            if stem_upper in mapa_2d:
                candidatos = mapa_2d[stem_upper]
                for cand in candidatos:
                    if os.path.dirname(cand) == dir_3d or "DESENHO" in cand.upper():
                        p2d_encontrado = cand
                        break
                if not p2d_encontrado and candidatos:
                    p2d_encontrado = candidatos[0]

            if p2d_encontrado:
                pares_2d_utilizados.add(p2d_encontrado)

            # Localiza PDF correspondente
            ppdf_encontrado = None
            if stem_upper in mapa_pdf:
                candidatos = mapa_pdf[stem_upper]
                for cand in candidatos:
                    if os.path.dirname(cand) == dir_3d or "PDF" in cand.upper():
                        ppdf_encontrado = cand
                        break
                if not ppdf_encontrado and candidatos:
                    ppdf_encontrado = candidatos[0]

            if ppdf_encontrado:
                pares_pdf_utilizados.add(ppdf_encontrado)

            # Extrai dados sugeridos
            cod_sug, nome_sug, tipo_sug = self.extrair_dados_de_arquivo(p3d)
            if not cod_sug and p2d_encontrado:
                cod_sug, _, _ = self.extrair_dados_de_arquivo(p2d_encontrado)

            ja_cad = bool(cod_sug and cod_sug.upper() in pecas_cadastradas)

            itens_detectados.append({
                "id": id_counter,
                "caminho_3d": p3d,
                "caminho_2d": p2d_encontrado,
                "caminho_pdf": ppdf_encontrado,
                "codigo": cod_sug or "",
                "nome": nome_sug,
                "tipo": tipo_sug,
                "tem_3d": True,
                "tem_2d": bool(p2d_encontrado),
                "tem_pdf": bool(ppdf_encontrado),
                "ja_cadastrado": ja_cad,
                "selecionado": not ja_cad and bool(cod_sug)
            })
            id_counter += 1

        # 3. Inclui 2D órfãos (desenhos técnicos sem 3D encontrado na pasta)
        for p2d in arquivos_2d:
            if p2d not in pares_2d_utilizados:
                stem_2d = os.path.splitext(os.path.basename(p2d))[0].strip()
                stem_upper = stem_2d.upper()

                ppdf_encontrado = None
                if stem_upper in mapa_pdf:
                    candidatos = mapa_pdf[stem_upper]
                    for cand in candidatos:
                        if cand not in pares_pdf_utilizados:
                            ppdf_encontrado = cand
                            break

                cod_sug, nome_sug, tipo_sug = self.extrair_dados_de_arquivo(p2d)
                ja_cad = bool(cod_sug and cod_sug.upper() in pecas_cadastradas)

                itens_detectados.append({
                    "id": id_counter,
                    "caminho_3d": None,
                    "caminho_2d": p2d,
                    "caminho_pdf": ppdf_encontrado,
                    "codigo": cod_sug or "",
                    "nome": nome_sug,
                    "tipo": tipo_sug,
                    "tem_3d": False,
                    "tem_2d": True,
                    "tem_pdf": bool(ppdf_encontrado),
                    "ja_cadastrado": ja_cad,
                    "selecionado": not ja_cad and bool(cod_sug)
                })
                id_counter += 1

        # Ordena: prontos/válidos primeiro, depois por código/nome
        itens_detectados.sort(key=lambda x: (x["codigo"] == "", x["codigo"], x["nome"]))
        return itens_detectados




