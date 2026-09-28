"""
Cliente de Integração com a API COM do SolidWorks.
Comunica-se com SldWorks.Application para criar peças, desenhos, salvar com código correto,
gerenciar propriedades personalizadas e exportar PDFs.
Trata todas as exceções de forma amigável para o usuário.
"""

import os
import sys
import glob
from typing import Tuple, Optional
from core.logger import registrar_log
from core.config import carregar_config
from cad.sw_properties import SWPropertyManager

# Constantes do SolidWorks API (swDocumentTypes_e)
SW_DOC_NONE = 0
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_DOC_DRAWING = 3

# Opções de abertura (swOpenDocOptions_e)
SW_OPENDOC_OPTIONS_SILENT = 1

# Opções de salvamento (swSaveAsOptions_e)
SW_SAVEAS_OPTIONS_SILENT = 1
SW_SAVEAS_OPTIONS_COPY = 2


class SolidWorksClient:
    def __init__(self, modo_simulacao: bool = False):
        self.modo_simulacao = modo_simulacao
        self._sw_app = None

    def conectar(self) -> Tuple[bool, str]:
        """
        Conecta ao SolidWorks via COM Automation no Windows.
        Tenta conectar a uma instância já aberta ou inicia uma nova.
        Garante que o SolidWorks fique visível e sob controle do usuário.
        """
        if self.modo_simulacao:
            return True, "Modo de simulação ativo (SolidWorks Virtual)."

        try:
            import win32com.client
            # Tenta pegar a instância em execução
            try:
                self._sw_app = win32com.client.GetActiveObject("SldWorks.Application")
            except Exception:
                # Se não estiver aberto, tenta iniciar
                self._sw_app = win32com.client.Dispatch("SldWorks.Application")

            if self._sw_app:
                try:
                    self._sw_app.Visible = True
                    self._sw_app.UserControl = True
                except Exception:
                    pass
                return True, "Conectado ao SolidWorks com sucesso."
            else:
                return False, "Não foi possível obter a interface do SolidWorks."

        except Exception as e:
            registrar_log(
                "ERRO CONEXAO SOLIDWORKS",
                {"ErroDetalhado": str(e)},
                nivel="ERROR"
            )
            return (
                False,
                f"Não foi possível conectar ao SolidWorks.\n\n"
                f"Detalhe: {e}\n\n"
                "Verifique se o SolidWorks está instalado e tente novamente."
            )

    def esta_conectado(self) -> bool:
        """Verifica se o cliente está conectado e respondendo sem disparar exceção em métodos/propriedades."""
        if self.modo_simulacao:
            return True
        if self._sw_app is None:
            return False
        try:
            # Testa liveness seguro
            rev = getattr(self._sw_app, "RevisionNumber", None)
            if rev is not None:
                return True
            vis = getattr(self._sw_app, "Visible", None)
            return vis is not None
        except Exception:
            self._sw_app = None
            return False

    def _obter_caminho_template(self, tipo: str, template_custom: str = "") -> str:
        """
        Localiza o melhor caminho de template (.PRTDOT, .ASMDOT ou .DRWDOT).
        Procura na configuração customizada, nas preferências do usuário no SolidWorks,
        na API de templates e nos diretórios padrão do SolidWorks no sistema.
        """
        if template_custom and os.path.exists(template_custom):
            return template_custom

        tipo_lower = tipo.lower()
        is_drawing = tipo_lower in ("desenho", "drawing", "drw")
        is_assembly = (tipo_lower == "montagem")
        
        # 1. Verifica config.json
        cfg = carregar_config()
        if is_drawing:
            cfg_key = "template_desenho"
        elif is_assembly:
            cfg_key = "template_montagem"
        else:
            cfg_key = "template_peca"
            
        cfg_template = cfg.get(cfg_key, "")
        if cfg_template and os.path.exists(cfg_template):
            return cfg_template

        # 2. Verifica preferências do SolidWorks (15 = Part, 16 = Assembly, 17 = Drawing)
        if is_drawing:
            pref_id = 17
            doc_type_const = SW_DOC_DRAWING
        elif is_assembly:
            pref_id = 16
            doc_type_const = SW_DOC_ASSEMBLY
        else:
            pref_id = 15
            doc_type_const = SW_DOC_PART

        if self._sw_app:
            try:
                sw_pref = self._sw_app.GetUserPreferenceStringValue(pref_id)
                if sw_pref and os.path.exists(sw_pref):
                    return sw_pref
            except Exception:
                pass

            # 3. Tenta API GetDocumentTemplate
            try:
                sw_tmpl = self._sw_app.GetDocumentTemplate(doc_type_const, "", 0, 0, 0)
                if sw_tmpl and os.path.exists(sw_tmpl):
                    return sw_tmpl
            except Exception:
                pass

        # 4. Busca em diretórios padrão do SolidWorks no Windows (ProgramData, Program Files)
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        nomes_part = ["Peça.PRTDOT", "Peca.PRTDOT", "Part.prtdot", "Part.PRTDOT", "Peça.prtdot", "Peca.prtdot"]
        nomes_asm = ["Montagem.ASMDOT", "Assembly.asmdot", "Assembly.ASMDOT", "Montagem.asmdot"]
        nomes_drw = ["Desenho.DRWDOT", "Desenho.drwdot", "Draw.drwdot", "Draw.DRWDOT", "Drawing.drwdot", "Drawing.DRWDOT"]

        if is_drawing:
            nomes_alvo = nomes_drw
        elif is_assembly:
            nomes_alvo = nomes_asm
        else:
            nomes_alvo = nomes_part

        candidatos = []
        for nome in nomes_alvo:
            candidatos.extend(glob.glob(f"{program_data}\\SolidWorks\\*\\templates\\{nome}"))
            candidatos.extend(glob.glob(f"{program_data}\\SOLIDWORKS\\*\\templates\\{nome}"))
            candidatos.extend(glob.glob(f"{program_files}\\SOLIDWORKS Corp\\*\\templates\\{nome}"))
            candidatos.extend(glob.glob(f"{program_files}\\SOLIDWORKS Corp\\*\\*\\templates\\{nome}"))
            candidatos.extend(glob.glob(f"{program_files}\\SOLIDWORKS Corp\\*\\data\\templates\\{nome}"))

        for c in candidatos:
            if os.path.exists(c):
                return c

        return ""

    def criar_novo_desenho_cad(
        self,
        codigo: str,
        nome: str,
        tipo: str,
        caminho_salvar_desenho: str,
        caminho_modelo_cad: str = "",
        template_custom: str = ""
    ) -> Tuple[bool, str]:
        """
        Cria um novo documento de Desenho 2D (.SLDDRW),
        vincula ao modelo 3D (se existente), preenche as Custom Properties
        e salva automaticamente no caminho da pasta DESENHO (ex: ...\\DESENHO\\250.001.SLDDRW).
        Dessa forma, ao trabalhar no desenho e salvar no SolidWorks, ele nunca pede pasta.
        """
        if self.modo_simulacao:
            try:
                os.makedirs(os.path.dirname(caminho_salvar_desenho), exist_ok=True)
                with open(caminho_salvar_desenho, "w", encoding="utf-8") as f:
                    f.write(f"[SIMULAÇÃO DESENHO 2D SOLIDWORKS]\nCODIGO={codigo}\nNOME={nome}\nTIPO={tipo}\nREVISAO=A\nMODELO={caminho_modelo_cad}\n")
                return True, f"Desenho 2D simulado criado em:\n{caminho_salvar_desenho}"
            except Exception as e:
                return False, f"Erro ao criar arquivo simulado: {e}"

        conectado, msg_conn = self.conectar()
        if not conectado:
            return False, msg_conn

        try:
            template_path = self._obter_caminho_template("desenho", template_custom)

            drw_doc = None
            if template_path:
                try:
                    drw_doc = self._sw_app.NewDocument(template_path, 0, 0, 0)
                except Exception:
                    try:
                        drw_doc = self._sw_app.INewDocument2(template_path, 0, 0, 0)
                    except Exception:
                        pass

            if not drw_doc:
                try:
                    drw_doc = self._sw_app.NewDocument("", 0, 0, 0)
                except Exception:
                    pass

            if not drw_doc:
                return (
                    False,
                    f"O SolidWorks não conseguiu criar o documento de desenho.\n\n"
                    f"Template procurado: {template_path or 'Não localizado'}\n\n"
                    f"Verifique se o template de desenho (Desenho.DRWDOT) existe no SolidWorks."
                )

            # Preenche Custom Properties padronizadas no desenho
            SWPropertyManager.gravar_propriedades_padrao(
                model_doc=drw_doc,
                codigo=codigo,
                descricao=nome,
                revisao="A",
                tipo=tipo
            )

            # Se o modelo 3D existir, tenta vincular/criar vistas padrão
            if caminho_modelo_cad and os.path.exists(caminho_modelo_cad):
                try:
                    _ = drw_doc.Create3rdAngleViews2(caminho_modelo_cad)
                except Exception:
                    pass

            # Salva o arquivo no caminho correto da pasta DESENHO
            os.makedirs(os.path.dirname(caminho_salvar_desenho), exist_ok=True)
            
            try:
                _ = drw_doc.SaveAs3(caminho_salvar_desenho, 0, 1)
            except Exception:
                try:
                    _ = drw_doc.SaveAs(caminho_salvar_desenho)
                except Exception as e_save:
                    registrar_log("AVISO SAVEAS DESENHO", {"Erro": str(e_save)}, nivel="WARNING")

            try:
                self._sw_app.Visible = True
                self._sw_app.UserControl = True
            except Exception:
                pass

            registrar_log(
                "DESENHO 2D CRIADO NO SOLIDWORKS",
                {
                    "Código": codigo,
                    "Nome": nome,
                    "Arquivo": caminho_salvar_desenho,
                    "Modelo": caminho_modelo_cad
                }
            )

            return True, f"Desenho 2D criado e salvo com sucesso em:\n{caminho_salvar_desenho}"

        except Exception as e:
            registrar_log(
                "ERRO CRIAR DESENHO SOLIDWORKS",
                {"Código": codigo, "Arquivo": caminho_salvar_desenho, "Erro": str(e)},
                nivel="ERROR"
            )
            return False, f"Ocorreu um problema ao criar o desenho no SolidWorks:\n{e}"

    def criar_novo_documento_cad(
        self,
        codigo: str,
        nome: str,
        tipo: str,
        caminho_salvar: str,
        template_custom: str = "",
        componentes: Optional[list] = None
    ) -> Tuple[bool, str]:
        """
        Cria um novo documento de Peça (.SLDPRT) ou Montagem (.SLDASM),
        grava as Custom Properties (CODIGO, DESCRICAO, REVISAO=A, TIPO, COMPONENTES_CO)
        e salva no caminho especificado (ex: ...\\CAD\\250.001.SLDPRT).
        """
        if self.modo_simulacao:
            try:
                os.makedirs(os.path.dirname(caminho_salvar), exist_ok=True)
                with open(caminho_salvar, "w", encoding="utf-8") as f:
                    f.write(f"[SIMULAÇÃO SOLIDWORKS]\nCODIGO={codigo}\nNOME={nome}\nTIPO={tipo}\nREVISAO=A\n")
                    if componentes:
                        comp_resumo = "; ".join([
                            f"{getattr(c, 'codigo', c.get('codigo', ''))} (x{getattr(c, 'quantidade', c.get('quantidade', 1))})"
                            for c in componentes
                        ])
                        f.write(f"COMPONENTES_CO={comp_resumo}\n")
                return True, f"Documento CAD simulado criado com sucesso em:\n{caminho_salvar}"
            except Exception as e:
                return False, f"Erro ao criar arquivo simulado: {e}"

        conectado, msg_conn = self.conectar()
        if not conectado:
            return False, msg_conn

        try:
            is_assembly = (tipo.lower() == "montagem")
            template_path = self._obter_caminho_template(tipo, template_custom)

            # Cria novo documento a partir do template
            model_doc = None
            if template_path:
                try:
                    model_doc = self._sw_app.NewDocument(template_path, 0, 0, 0)
                except Exception:
                    try:
                        model_doc = self._sw_app.INewDocument2(template_path, 0, 0, 0)
                    except Exception:
                        pass

            if not model_doc:
                # Tenta criação com NewDocument vazio
                try:
                    model_doc = self._sw_app.NewDocument("", 0, 0, 0)
                except Exception:
                    pass

            if not model_doc:
                return (
                    False,
                    f"O SolidWorks não conseguiu criar o documento.\n\n"
                    f"Template procurado: {template_path or 'Não localizado'}\n\n"
                    f"Configure o caminho do template padrão nas opções do SolidWorks ou na aba Configurações."
                )

            # Preenche Custom Properties padronizadas
            SWPropertyManager.gravar_propriedades_padrao(
                model_doc=model_doc,
                codigo=codigo,
                descricao=nome,
                revisao="A",
                tipo=tipo
            )

            # Se for montagem com componentes vinculados, grava a lista nas propriedades
            if componentes:
                comp_str = "; ".join([
                    f"{getattr(c, 'codigo', c.get('codigo', ''))} (x{getattr(c, 'quantidade', c.get('quantidade', 1))})"
                    for c in componentes
                ])
                SWPropertyManager.definir_propriedade(model_doc, "COMPONENTES_CO", comp_str)
                SWPropertyManager.definir_propriedade(model_doc, "QTD_COMPONENTES_CO", str(len(componentes)))

            # Salva no caminho correto da pasta CAD
            os.makedirs(os.path.dirname(caminho_salvar), exist_ok=True)
            
            # SaveAs3: (FileName, SaveAsVersion=0 (current), Options=1 (silent))
            try:
                res_save = model_doc.SaveAs3(caminho_salvar, 0, 1)
            except Exception:
                try:
                    res_save = model_doc.SaveAs(caminho_salvar)
                except Exception as e_save:
                    registrar_log(
                        "AVISO SAVEAS",
                        {"Erro": str(e_save)},
                        nivel="WARNING"
                    )

            # Exporta automaticamente o preview 3D da peça em PNG
            try:
                pasta_projeto = os.path.dirname(os.path.dirname(caminho_salvar))
                caminho_preview = os.path.join(pasta_projeto, "preview.png")
                _ = model_doc.SaveAs3(caminho_preview, 0, 2)
            except Exception:
                pass

            # Garante que o SolidWorks e a janela do documento fiquem visíveis para o usuário
            try:
                self._sw_app.Visible = True
                self._sw_app.UserControl = True
            except Exception:
                pass

            registrar_log(
                "DOCUMENTO CAD CRIADO NO SOLIDWORKS",
                {
                    "Código": codigo,
                    "Nome": nome,
                    "Arquivo": caminho_salvar,
                    "Tipo": tipo
                }
            )

            return True, f"Arquivo criado e configurado com sucesso no SolidWorks:\n{caminho_salvar}"

        except Exception as e:
            registrar_log(
                "ERRO CRIAR DOCUMENTO SOLIDWORKS",
                {"Código": codigo, "Arquivo": caminho_salvar, "Erro": str(e)},
                nivel="ERROR"
            )
            return False, f"Ocorreu um problema ao criar o documento no SolidWorks:\n{e}"

    def abrir_documento(self, caminho_arquivo: str) -> Tuple[bool, str]:
        """Abre um documento CAD (.SLDPRT, .SLDASM, .SLDDRW) no SolidWorks."""
        if not os.path.exists(caminho_arquivo):
            return False, f"O arquivo especificado não foi encontrado:\n{caminho_arquivo}"

        if self.modo_simulacao:
            try:
                os.startfile(caminho_arquivo)
                return True, f"Arquivo aberto (Modo Simulação): {os.path.basename(caminho_arquivo)}"
            except Exception as e:
                return False, f"Erro ao abrir arquivo: {e}"

        conectado, msg_conn = self.conectar()
        if not conectado:
            return False, msg_conn

        try:
            ext = os.path.splitext(caminho_arquivo)[1].upper()
            doc_type = SW_DOC_PART
            if ext == ".SLDASM":
                doc_type = SW_DOC_ASSEMBLY
            elif ext == ".SLDDRW":
                doc_type = SW_DOC_DRAWING

            import win32com.client
            errors = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)

            # OpenDoc6(FileName, Type, Options, Configuration, Errors, Warnings)
            model_doc = self._sw_app.OpenDoc6(caminho_arquivo, doc_type, 1, "", errors, warnings)
            if model_doc:
                try:
                    self._sw_app.Visible = True
                    self._sw_app.UserControl = True
                except Exception:
                    pass
                return True, f"Arquivo {os.path.basename(caminho_arquivo)} aberto com sucesso no SolidWorks."
            else:
                return False, f"Não foi possível abrir o arquivo no SolidWorks. Verifique se o arquivo não está corrompido."

        except Exception as e:
            registrar_log("ERRO ABRIR DOCUMENTO SOLIDWORKS", {"Arquivo": caminho_arquivo, "Erro": str(e)}, nivel="ERROR")
            return False, f"Erro ao solicitar abertura no SolidWorks:\n{e}"

    def fechar_documento(self, caminho_ou_nome: str) -> bool:
        """
        Fecha um documento no SolidWorks se estiver aberto, liberando o arquivo no Windows.
        """
        if self.modo_simulacao or not self._sw_app:
            return True
        try:
            nome_arquivo = os.path.basename(caminho_ou_nome)
            # Tenta fechar usando o nome do arquivo com extensão
            self._sw_app.CloseDoc(nome_arquivo)
            # Tenta fechar também pelo nome do documento sem extensão (título de janela SW)
            nome_sem_ext, _ = os.path.splitext(nome_arquivo)
            if nome_sem_ext != nome_arquivo:
                self._sw_app.CloseDoc(nome_sem_ext)
            # Tenta fechar pelo caminho completo
            self._sw_app.CloseDoc(caminho_ou_nome)
            return True
        except Exception as e:
            registrar_log("AVISO FECHAR DOCUMENTO SW", {"Doc": caminho_ou_nome, "Erro": str(e)}, nivel="WARNING")
            return False

    def fechar_documentos_da_pasta(self, pasta_caminho: str) -> None:
        """
        Varre a pasta e fecha qualquer arquivo CAD ou Desenho que esteja aberto no SolidWorks.
        """
        if self.modo_simulacao or not self._sw_app or not os.path.isdir(pasta_caminho):
            return
        try:
            for raiz, _, arquivos in os.walk(pasta_caminho):
                for arq in arquivos:
                    ext = os.path.splitext(arq)[1].upper()
                    if ext in [".SLDPRT", ".SLDASM", ".SLDDRW"]:
                        caminho_completo = os.path.join(raiz, arq)
                        self.fechar_documento(caminho_completo)
        except Exception as e:
            registrar_log("AVISO FECHAR DOCS DA PASTA SW", {"Pasta": pasta_caminho, "Erro": str(e)}, nivel="WARNING")

    def atualizar_revisao_no_arquivo(self, caminho_arquivo: str, nova_revisao: str) -> Tuple[bool, str]:
        """Abre o arquivo no SolidWorks e atualiza a propriedade REVISAO."""
        if self.modo_simulacao:
            return True, "Revisão atualizada na simulação."

        conectado, msg_conn = self.conectar()
        if not conectado:
            return False, msg_conn

        try:
            ext = os.path.splitext(caminho_arquivo)[1].upper()
            doc_type = SW_DOC_PART if ext == ".SLDPRT" else SW_DOC_ASSEMBLY

            import win32com.client
            errors = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)

            model_doc = self._sw_app.OpenDoc6(caminho_arquivo, doc_type, 1, "", errors, warnings)
            if model_doc:
                SWPropertyManager.definir_propriedade(model_doc, "REVISAO", nova_revisao)
                model_doc.Save3(1, errors, warnings)
                return True, f"Propriedade REVISAO atualizada para {nova_revisao} no arquivo CAD."
            return False, "Não foi possível carregar o arquivo para atualizar a propriedade."
        except Exception as e:
            return False, f"Erro ao atualizar propriedade de revisão no arquivo: {e}"

    def gerar_pdf_de_desenho(self, caminho_desenho: str, caminho_pdf_destino: str) -> Tuple[bool, str]:
        """
        Abre o desenho .SLDDRW e exporta como .pdf na pasta PDF.
        """
        if not os.path.exists(caminho_desenho):
            return False, f"Arquivo de desenho não encontrado:\n{caminho_desenho}"

        if self.modo_simulacao:
            try:
                os.makedirs(os.path.dirname(caminho_pdf_destino), exist_ok=True)
                with open(caminho_pdf_destino, "w", encoding="utf-8") as f:
                    f.write(f"[SIMULAÇÃO PDF]\nOrigem={caminho_desenho}\n")
                return True, f"PDF simulado gerado em: {caminho_pdf_destino}"
            except Exception as e:
                return False, f"Erro ao gerar PDF simulado: {e}"

        conectado, msg_conn = self.conectar()
        if not conectado:
            return False, msg_conn

        try:
            import win32com.client
            errors = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(win32com.client.pythoncom.VT_BYREF | win32com.client.pythoncom.VT_I4, 0)

            # Verifica se o desenho já estava aberto na sessão do SolidWorks
            ja_estava_aberto = False
            try:
                nome_base = os.path.basename(caminho_desenho)
                doc_aberto = self._sw_app.GetOpenDocumentByName(caminho_desenho)
                if not doc_aberto:
                    doc_aberto = self._sw_app.GetOpenDocumentByName(nome_base)
                if doc_aberto:
                    ja_estava_aberto = True
            except Exception:
                pass

            model_doc = self._sw_app.OpenDoc6(caminho_desenho, SW_DOC_DRAWING, 1, "", errors, warnings)
            if not model_doc:
                return False, "Não foi possível abrir o desenho para exportar o PDF."

            os.makedirs(os.path.dirname(caminho_pdf_destino), exist_ok=True)

            # Exportação para PDF via SaveAs3 (0 = swSaveAsCurrentVersion, 2 = swSaveAsOptions_Silent)
            res = model_doc.SaveAs3(caminho_pdf_destino, 0, 2)

            # Se o documento foi aberto em background apenas para exportar o PDF, fecha para liberar recursos
            if not ja_estava_aberto:
                try:
                    self._sw_app.CloseDoc(os.path.basename(caminho_desenho))
                except Exception:
                    pass
            
            registrar_log(
                "PDF GERADO",
                {
                    "Desenho": caminho_desenho,
                    "PDF": caminho_pdf_destino
                }
            )

            return True, f"PDF gerado com sucesso em:\n{caminho_pdf_destino}"

        except Exception as e:
            registrar_log("ERRO GERAR PDF", {"Desenho": caminho_desenho, "Erro": str(e)}, nivel="ERROR")
            return False, f"Erro ao gerar PDF a partir do SolidWorks:\n{e}"

