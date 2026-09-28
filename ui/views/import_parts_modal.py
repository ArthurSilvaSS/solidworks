"""
Modal para Importação de Peças Prontas (3D e 2D) no Controle CAD.
Permite importar projetos e desenhos já prontos do SolidWorks:
1. Modo Peça Individual: Seleção de arquivos 3D (.SLDPRT/.SLDASM) e 2D (.SLDDRW), com preenchimento automático.
2. Modo Importação em Lote: Varredura de pasta externa com pareamento automático de 3D+2D e importação em massa.
"""

import os
from typing import Callable, Optional, List, Dict, Any
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.models import PecaInfo, ComponenteItem, LINHAS_PRODUTO
from core.validator import validar_codigo, validar_nome_peca
from services.storage_service import StorageService
from ui.views.select_components_modal import SelectComponentsModal


class ImportPartsModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        storage_service: StorageService,
        on_success_callback: Callable[[PecaInfo], None],
        sw_client=None,
        pdf_service=None
    ):
        super().__init__(parent)
        self.parent = parent
        self.storage = storage_service
        self.on_success = on_success_callback
        self.sw_client = sw_client
        self.pdf_service = pdf_service

        self.componentes_selecionados: List[ComponenteItem] = []
        self.itens_lote_detectados: List[Dict[str, Any]] = []
        self.widgets_linha_lote: List[Dict[str, Any]] = []

        self.title("Importar Peças Prontas (3D e 2D) — Controle CAD")

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        largura = min(sw - 40, 940)
        altura = min(sh - 60, 720)
        self.geometry(f"{largura}x{altura}")
        self.minsize(720, 520)
        self.resizable(True, True)

        self.grab_set()
        self.transient(parent)

        self._construir_ui()

    def _construir_ui(self):
        # 1. CABEÇALHO
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(16, 8))

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text="📥 IMPORTAR PEÇAS PRONTAS (3D E 2D)",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#1f6aa5", "#4ea8de")
        )
        lbl_titulo.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            header_frame,
            text="Adicione peças, montagens e componentes comerciais já desenhados no SolidWorks diretamente ao padrão do sistema.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        lbl_desc.pack(anchor="w", pady=(2, 0))

        # 2. SELETOR DE MODO (ABA / SEGMENTED BUTTON)
        modo_frame = ctk.CTkFrame(self, fg_color="transparent")
        modo_frame.pack(fill="x", padx=25, pady=(0, 10))

        self.seg_modo = ctk.CTkSegmentedButton(
            modo_frame,
            values=["📄 Peça Individual (3D + 2D)", "📂 Importar em Lote (Escanear Pasta)"],
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            command=self._ao_alternar_modo
        )
        self.seg_modo.set("📄 Peça Individual (3D + 2D)")
        self.seg_modo.pack(fill="x")

        # 3. CONTAINER DE CONTEÚDO (Muda conforme a aba)
        self.container_conteudo = ctk.CTkFrame(self, fg_color="transparent")
        self.container_conteudo.pack(fill="both", expand=True, padx=25, pady=(0, 5))

        # Constrói as duas visões
        self._construir_visao_individual()
        self._construir_visao_lote()

        # Exibe inicialmente a visão individual
        self._mostrar_visao_individual()

    # =========================================================================
    # VISÃO 1: IMPORTAÇÃO INDIVIDUAL (PEÇA ÚNICA)
    # =========================================================================
    def _construir_visao_individual(self):
        self.frame_individual = ctk.CTkFrame(self.container_conteudo, fg_color="transparent")

        # Rodapé fixo com botões de ação
        rodape_indiv = ctk.CTkFrame(self.frame_individual, fg_color="transparent")
        rodape_indiv.pack(fill="x", side="bottom", pady=(6, 12))

        btn_cancelar = ctk.CTkButton(
            rodape_indiv,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=38,
            command=self.destroy
        )
        btn_cancelar.pack(side="left")

        self.btn_importar_indiv = ctk.CTkButton(
            rodape_indiv,
            text="📥 IMPORTAR PROJETO NO SISTEMA ➔",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#d9822b",
            hover_color="#b8691b",
            width=240,
            height=38,
            command=self._executar_importacao_individual
        )
        self.btn_importar_indiv.pack(side="right")

        # Corpo rolável
        self.scroll_indiv = ctk.CTkScrollableFrame(self.frame_individual, corner_radius=10)
        self.scroll_indiv.pack(fill="both", expand=True, pady=(0, 6))

        # CARD 1: SELEÇÃO DE ARQUIVOS DE ORIGEM
        card_arquivos = ctk.CTkFrame(self.scroll_indiv, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        card_arquivos.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(
            card_arquivos,
            text="1. Arquivos de Engenharia (3D e 2D)",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 6))

        # Linha Modelo 3D
        lbl_3d = ctk.CTkLabel(card_arquivos, text="Modelo 3D (.SLDPRT ou .SLDASM):", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_3d.pack(anchor="w", padx=15, pady=(4, 2))

        linha_3d = ctk.CTkFrame(card_arquivos, fg_color="transparent")
        linha_3d.pack(fill="x", padx=15, pady=(0, 6))

        self.entry_caminho_3d = ctk.CTkEntry(
            linha_3d,
            placeholder_text="Selecione o arquivo 3D...",
            font=ctk.CTkFont(size=12),
            height=34
        )
        self.entry_caminho_3d.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_proc_3d = ctk.CTkButton(
            linha_3d,
            text="Procurar 3D...",
            width=120,
            height=34,
            command=self._selecionar_arquivo_3d
        )
        btn_proc_3d.pack(side="right")

        # Feedback detecção automática 2D
        self.lbl_auto_detect_2d = ctk.CTkLabel(
            card_arquivos,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2fa572"
        )
        self.lbl_auto_detect_2d.pack(anchor="w", padx=15, pady=(0, 4))

        # Linha Desenho Técnico 2D
        lbl_2d = ctk.CTkLabel(card_arquivos, text="Desenho Técnico 2D (.SLDDRW):", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_2d.pack(anchor="w", padx=15, pady=(4, 2))

        linha_2d = ctk.CTkFrame(card_arquivos, fg_color="transparent")
        linha_2d.pack(fill="x", padx=15, pady=(0, 6))

        self.entry_caminho_2d = ctk.CTkEntry(
            linha_2d,
            placeholder_text="Selecione o arquivo de desenho 2D...",
            font=ctk.CTkFont(size=12),
            height=34
        )
        self.entry_caminho_2d.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_proc_2d = ctk.CTkButton(
            linha_2d,
            text="Procurar 2D...",
            width=120,
            height=34,
            command=self._selecionar_arquivo_2d
        )
        btn_proc_2d.pack(side="right")

        # Linha Arquivo PDF (Opcional)
        lbl_pdf = ctk.CTkLabel(card_arquivos, text="Arquivo PDF (.pdf) [Opcional]:", font=ctk.CTkFont(size=12))
        lbl_pdf.pack(anchor="w", padx=15, pady=(4, 2))

        linha_pdf = ctk.CTkFrame(card_arquivos, fg_color="transparent")
        linha_pdf.pack(fill="x", padx=15, pady=(0, 12))

        self.entry_caminho_pdf = ctk.CTkEntry(
            linha_pdf,
            placeholder_text="PDF já gerado anteriormente (opcional)...",
            font=ctk.CTkFont(size=12),
            height=34
        )
        self.entry_caminho_pdf.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_proc_pdf = ctk.CTkButton(
            linha_pdf,
            text="Procurar PDF...",
            width=120,
            height=34,
            fg_color="#444444",
            hover_color="#333333",
            command=self._selecionar_arquivo_pdf
        )
        btn_proc_pdf.pack(side="right")

        # CARD 2: DADOS CADASTRAIS PADRONIZADOS
        card_dados = ctk.CTkFrame(self.scroll_indiv, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        card_dados.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            card_dados,
            text="2. Dados do Projeto no Sistema",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 6))

        # Linha de Produto
        ctk.CTkLabel(card_dados, text="Linha de Produto:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.combo_linha = ctk.CTkComboBox(
            card_dados,
            values=LINHAS_PRODUTO,
            state="readonly",
            height=36,
            font=ctk.CTkFont(size=13),
        )
        self.combo_linha.set("MedicalFix")
        self.combo_linha.pack(fill="x", padx=15, pady=(0, 8))

        # Tipo de Documento
        ctk.CTkLabel(card_dados, text="Tipo de Documento:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.combo_tipo = ctk.CTkComboBox(
            card_dados,
            values=["Peça", "Montagem", "CO"],
            state="readonly",
            height=36,
            font=ctk.CTkFont(size=13),
            command=self._ao_mudar_tipo_indiv
        )
        self.combo_tipo.set("Peça")
        self.combo_tipo.pack(fill="x", padx=15, pady=(0, 8))

        # Código da Peça
        self.lbl_codigo_titulo = ctk.CTkLabel(card_dados, text="Código da Peça (000.000):", font=ctk.CTkFont(weight="bold"))
        self.lbl_codigo_titulo.pack(anchor="w", padx=15, pady=(4, 2))

        self.entry_codigo = ctk.CTkEntry(
            card_dados,
            placeholder_text="Ex: 250.001",
            font=ctk.CTkFont(size=13, family="Consolas"),
            height=36
        )
        self.entry_codigo.pack(fill="x", padx=15, pady=(0, 2))

        self.lbl_codigo_hint = ctk.CTkLabel(
            card_dados,
            text="Formato: 3 números, ponto, 3 números (ex: 250.001)",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.lbl_codigo_hint.pack(anchor="w", padx=15, pady=(0, 8))

        # Nome da Peça
        self.lbl_nome_titulo = ctk.CTkLabel(card_dados, text="Nome da Peça:", font=ctk.CTkFont(weight="bold"))
        self.lbl_nome_titulo.pack(anchor="w", padx=15, pady=(4, 2))

        self.entry_nome = ctk.CTkEntry(
            card_dados,
            placeholder_text="Ex: Suporte Motor",
            font=ctk.CTkFont(size=13),
            height=36
        )
        self.entry_nome.pack(fill="x", padx=15, pady=(0, 8))

        # Descrição Detalhada
        ctk.CTkLabel(card_dados, text="Descrição Detalhada:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        self.entry_descricao = ctk.CTkEntry(
            card_dados,
            placeholder_text="Ex: Suporte em chapa de aço 3mm...",
            font=ctk.CTkFont(size=13),
            height=36
        )
        self.entry_descricao.pack(fill="x", padx=15, pady=(0, 8))

        # Revisão Inicial
        linha_rev = ctk.CTkFrame(card_dados, fg_color="transparent")
        linha_rev.pack(fill="x", padx=15, pady=(0, 8))

        ctk.CTkLabel(linha_rev, text="Revisão Inicial:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.entry_revisao = ctk.CTkEntry(
            linha_rev,
            placeholder_text="A",
            width=60,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.entry_revisao.insert(0, "A")
        self.entry_revisao.pack(side="left")

        # Kits
        ctk.CTkLabel(card_dados, text="Kits Vinculados (opcional):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(4, 2))
        linha_kits = ctk.CTkFrame(card_dados, fg_color="transparent")
        linha_kits.pack(fill="x", padx=15, pady=(0, 8))

        self.entry_kits = ctk.CTkEntry(
            linha_kits,
            placeholder_text="Ex: Kit Cirúrgico, Kit Implante",
            font=ctk.CTkFont(size=13),
            height=36
        )
        self.entry_kits.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_kits = ctk.CTkButton(
            linha_kits,
            text="🏷️ Escolher...",
            width=110,
            height=36,
            fg_color="#334d66",
            hover_color="#24384a",
            command=self._abrir_seletor_kits
        )
        btn_kits.pack(side="right")

        # Painel Componentes CO (para Montagens)
        self.frame_comp_montagem = ctk.CTkFrame(card_dados, fg_color=("#e5e5e5", "#252a32"), corner_radius=6)
        lbl_c_tit = ctk.CTkLabel(self.frame_comp_montagem, text="📦 Componentes Comerciais (CO):", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_c_tit.pack(anchor="w", padx=10, pady=(6, 2))

        linha_comp = ctk.CTkFrame(self.frame_comp_montagem, fg_color="transparent")
        linha_comp.pack(fill="x", padx=10, pady=(0, 6))

        self.lbl_comp_status = ctk.CTkLabel(linha_comp, text="Nenhum CO selecionado", font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_comp_status.pack(side="left", fill="x", expand=True)

        btn_cos = ctk.CTkButton(
            linha_comp,
            text="🔍 Selecionar COs...",
            width=130,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._abrir_modal_cos
        )
        btn_cos.pack(side="right")

        # CARD 3: OPÇÕES DE IMPORTAÇÃO
        card_opcoes = ctk.CTkFrame(self.scroll_indiv, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        card_opcoes.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            card_opcoes,
            text="3. Opções de Arquivos",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 6))

        self.var_copiar = ctk.BooleanVar(value=True)
        chk_copiar = ctk.CTkCheckBox(
            card_opcoes,
            text="Copiar arquivos para a pasta do sistema (mantém os originais intactos como backup)",
            variable=self.var_copiar,
            font=ctk.CTkFont(size=12)
        )
        chk_copiar.pack(anchor="w", padx=15, pady=(2, 6))

        self.var_gerar_pdf = ctk.BooleanVar(value=True)
        chk_pdf = ctk.CTkCheckBox(
            card_opcoes,
            text="Gerar PDF automaticamente via SolidWorks se o PDF ainda não existir",
            variable=self.var_gerar_pdf,
            font=ctk.CTkFont(size=12)
        )
        chk_pdf.pack(anchor="w", padx=15, pady=(2, 12))

    def _ao_mudar_tipo_indiv(self, valor: str):
        if valor.upper() == "CO":
            self.lbl_codigo_titulo.configure(text="Código do Componente (CO-0000):")
            self.entry_codigo.configure(placeholder_text="Ex: CO-0001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório para Componente: CO-0000 (ex: CO-0001)")
            self.lbl_nome_titulo.configure(text="Nome do Componente:")
            self.frame_comp_montagem.pack_forget()
        elif valor.upper() == "MONTAGEM":
            self.lbl_codigo_titulo.configure(text="Código da Montagem (000.000):")
            self.entry_codigo.configure(placeholder_text="Ex: 250.001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório: 3 números, ponto, 3 números (000.000)")
            self.lbl_nome_titulo.configure(text="Nome da Montagem:")
            self.frame_comp_montagem.pack(fill="x", padx=15, pady=(0, 10))
        else:
            self.lbl_codigo_titulo.configure(text=f"Código da {valor} (000.000):")
            self.entry_codigo.configure(placeholder_text="Ex: 250.001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório: 3 números, ponto, 3 números (000.000)")
            self.lbl_nome_titulo.configure(text=f"Nome da {valor}:")
            self.frame_comp_montagem.pack_forget()

    def _selecionar_arquivo_3d(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar Modelo 3D (SolidWorks)",
            filetypes=[
                ("Modelos SolidWorks (*.SLDPRT;*.SLDASM)", "*.SLDPRT;*.SLDASM"),
                ("Peças SolidWorks (*.SLDPRT)", "*.SLDPRT"),
                ("Montagens SolidWorks (*.SLDASM)", "*.SLDASM"),
                ("Todos os Arquivos", "*.*")
            ],
            parent=self
        )
        if not caminho:
            return

        self.entry_caminho_3d.delete(0, "end")
        self.entry_caminho_3d.insert(0, os.path.normpath(caminho))

        # Analisa o nome do arquivo para sugerir dados
        cod_sug, nome_sug, tipo_sug = StorageService.extrair_dados_de_arquivo(caminho)

        if tipo_sug:
            self.combo_tipo.set(tipo_sug)
            self._ao_mudar_tipo_indiv(tipo_sug)

        if cod_sug:
            self.entry_codigo.delete(0, "end")
            self.entry_codigo.insert(0, cod_sug)

        if nome_sug:
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, nome_sug)
            if not self.entry_descricao.get():
                self.entry_descricao.delete(0, "end")
                self.entry_descricao.insert(0, nome_sug)

        # Busca automática do par 2D na mesma pasta
        dir_origem = os.path.dirname(caminho)
        stem = os.path.splitext(os.path.basename(caminho))[0]

        cand_2d = [
            os.path.join(dir_origem, f"{stem}.SLDDRW"),
            os.path.join(dir_origem, f"{stem}.slddrw"),
            os.path.join(dir_origem, "DESENHO", f"{stem}.SLDDRW"),
            os.path.join(dir_origem, "DESENHOS", f"{stem}.SLDDRW"),
        ]
        if cod_sug:
            cand_2d.append(os.path.join(dir_origem, f"{cod_sug}.SLDDRW"))

        achou_2d = False
        for c in cand_2d:
            if os.path.isfile(c):
                self.entry_caminho_2d.delete(0, "end")
                self.entry_caminho_2d.insert(0, os.path.normpath(c))
                self.lbl_auto_detect_2d.configure(text=f"✓ Desenho 2D encontrado automaticamente: {os.path.basename(c)}")
                achou_2d = True
                break

        if not achou_2d:
            self.lbl_auto_detect_2d.configure(text="")

        # Busca automática do PDF na mesma pasta
        cand_pdf = [
            os.path.join(dir_origem, f"{stem}.pdf"),
            os.path.join(dir_origem, f"{stem}.PDF"),
            os.path.join(dir_origem, "PDF", f"{stem}.pdf"),
        ]
        if cod_sug:
            cand_pdf.append(os.path.join(dir_origem, f"{cod_sug}.pdf"))

        for c in cand_pdf:
            if os.path.isfile(c):
                self.entry_caminho_pdf.delete(0, "end")
                self.entry_caminho_pdf.insert(0, os.path.normpath(c))
                break

    def _selecionar_arquivo_2d(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar Desenho Técnico 2D (SolidWorks)",
            filetypes=[
                ("Desenhos SolidWorks (*.SLDDRW)", "*.SLDDRW"),
                ("Todos os Arquivos", "*.*")
            ],
            parent=self
        )
        if caminho:
            self.entry_caminho_2d.delete(0, "end")
            self.entry_caminho_2d.insert(0, os.path.normpath(caminho))

            # Se código ainda não foi preenchido, tenta extrair do 2D
            if not self.entry_codigo.get().strip():
                cod_sug, nome_sug, tipo_sug = StorageService.extrair_dados_de_arquivo(caminho)
                if cod_sug:
                    self.entry_codigo.insert(0, cod_sug)
                if nome_sug and not self.entry_nome.get().strip():
                    self.entry_nome.insert(0, nome_sug)

    def _selecionar_arquivo_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar Arquivo PDF",
            filetypes=[("Arquivos PDF (*.pdf)", "*.pdf"), ("Todos os Arquivos", "*.*")],
            parent=self
        )
        if caminho:
            self.entry_caminho_pdf.delete(0, "end")
            self.entry_caminho_pdf.insert(0, os.path.normpath(caminho))

    def _abrir_seletor_kits(self):
        linha_atual = self.combo_linha.get() if hasattr(self, "combo_linha") else "MedicalFix"
        kits_cadastrados = self.storage.obter_todos_kits(linha=linha_atual)
        kits_ja_digitados = [k.strip() for k in self.entry_kits.get().split(",") if k.strip()]

        popup = ctk.CTkToplevel(self)
        popup.title(f"Selecionar Kits — {linha_atual}")
        popup.geometry("380x420")
        popup.resizable(False, False)
        popup.grab_set()
        popup.transient(self)

        ctk.CTkLabel(popup, text=f"Vincular aos Kits ({linha_atual}):", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=(15, 5), anchor="w")

        scroll = ctk.CTkScrollableFrame(popup, height=260)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        chk_vars = {}
        for kit_nome in kits_cadastrados:
            var = ctk.BooleanVar(value=any(k.lower() == kit_nome.lower() for k in kits_ja_digitados))
            chk_vars[kit_nome] = var
            linha = ctk.CTkFrame(scroll, fg_color="transparent")
            linha.pack(fill="x", pady=2)
            ctk.CTkCheckBox(linha, text=f"🏷️  {kit_nome}", variable=var, font=ctk.CTkFont(size=12)).pack(side="left", padx=5)

        def _confirmar():
            selecionados = [k for k, v in chk_vars.items() if v.get()]
            self.entry_kits.delete(0, "end")
            self.entry_kits.insert(0, ", ".join(selecionados))
            popup.destroy()

        ctk.CTkButton(popup, text="CONFIRMAR", font=ctk.CTkFont(weight="bold"), height=36, command=_confirmar).pack(fill="x", padx=20, pady=(0, 15))

    def _abrir_modal_cos(self):
        def _ao_confirmar(componentes: List[ComponenteItem]):
            self.componentes_selecionados = componentes
            qtd = len(componentes)
            if qtd == 0:
                self.lbl_comp_status.configure(text="Nenhum CO selecionado", text_color="gray")
            else:
                total_unidades = sum(c.quantidade for c in componentes)
                self.lbl_comp_status.configure(text=f"✓ {qtd} CO(s) vinculados ({total_unidades} un)", text_color="#2fa572")

        SelectComponentsModal(
            parent=self,
            storage_service=self.storage,
            on_confirm_callback=_ao_confirmar,
            componentes_iniciais=self.componentes_selecionados,
            codigo_montagem=self.entry_codigo.get().strip(),
            nome_montagem=self.entry_nome.get().strip()
        )

    def _executar_importacao_individual(self):
        caminho_3d = self.entry_caminho_3d.get().strip() or None
        caminho_2d = self.entry_caminho_2d.get().strip() or None
        caminho_pdf = self.entry_caminho_pdf.get().strip() or None

        if not caminho_3d and not caminho_2d:
            messagebox.showerror(
                "Arquivos Necessários",
                "Por favor, selecione pelo menos o Modelo 3D (.SLDPRT/.SLDASM) ou o Desenho 2D (.SLDDRW).",
                parent=self
            )
            return

        codigo = self.entry_codigo.get().strip()
        nome = self.entry_nome.get().strip()
        tipo = self.combo_tipo.get()
        descricao = self.entry_descricao.get().strip() or nome
        revisao = self.entry_revisao.get().strip().upper() or "A"
        copiar = self.var_copiar.get()

        kits_str = self.entry_kits.get().strip()
        kits_list = [k.strip() for k in kits_str.split(",") if k.strip()] if kits_str else []

        # Validação do código
        val_cod, msg_cod = validar_codigo(codigo, tipo=tipo)
        if not val_cod:
            messagebox.showerror("Código Inválido", msg_cod, parent=self)
            self.entry_codigo.focus()
            return

        # Validação do nome
        val_nome, msg_nome = validar_nome_peca(nome)
        if not val_nome:
            messagebox.showerror("Nome Inválido", msg_nome, parent=self)
            self.entry_nome.focus()
            return

        # Desabilita botão durante o processo
        self.btn_importar_indiv.configure(state="disabled", text="Importando arquivos...")
        self.update_idletasks()

        linha_produto = self.combo_linha.get() if hasattr(self, "combo_linha") else "MedicalFix"

        sucesso, peca, msg = self.storage.importar_peca_existente(
            caminho_3d=caminho_3d,
            caminho_2d=caminho_2d,
            caminho_pdf=caminho_pdf,
            codigo=codigo,
            nome=nome,
            tipo=tipo,
            descricao=descricao,
            revisao=revisao,
            kits=kits_list,
            componentes=self.componentes_selecionados if tipo.upper() == "MONTAGEM" else None,
            copiar=copiar,
            linha_produto=linha_produto
        )

        if not sucesso:
            self.btn_importar_indiv.configure(state="normal", text="📥 IMPORTAR PROJETO NO SISTEMA ➔")
            messagebox.showerror("Erro ao Importar", msg, parent=self)
            return

        # Se solicitado e o PDF ainda não existir, tenta gerar o PDF automaticamente se houver SW
        if self.var_gerar_pdf.get() and not caminho_pdf and self.pdf_service:
            try:
                precisa, _ = self.storage.peca_precisa_gerar_pdf(peca)
                if precisa:
                    ok_pdf, _ = self.pdf_service.processar_peca(peca)
                    if ok_pdf:
                        peca = self.storage.carregar_peca_por_pasta(peca.pasta_path) or peca
            except Exception:
                pass

        messagebox.showinfo(
            "Importação Concluída",
            f"✓ Projeto {codigo} - {nome} importado com sucesso!\n\n"
            f"• Linha de Produto: {linha_produto}\n"
            f"• Pasta criada: {os.path.basename(peca.pasta_path)}\n"
            f"• Modelo 3D: {'Sim' if caminho_3d else 'Não'}\n"
            f"• Desenho 2D: {'Sim' if caminho_2d else 'Não'}\n"
            f"• Modo: {'Cópia (backup seguro)' if copiar else 'Movimentação'}",
            parent=self.parent
        )

        if self.on_success:
            self.on_success(peca)
        self.destroy()

    # =========================================================================
    # VISÃO 2: IMPORTAÇÃO EM LOTE (VARREDURA DE PASTA EXTERNA)
    # =========================================================================
    def _construir_visao_lote(self):
        self.frame_lote = ctk.CTkFrame(self.container_conteudo, fg_color="transparent")

        # Rodapé fixo da visão em lote
        rodape_lote = ctk.CTkFrame(self.frame_lote, fg_color="transparent")
        rodape_lote.pack(fill="x", side="bottom", pady=(6, 12))

        btn_cancelar = ctk.CTkButton(
            rodape_lote,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=38,
            command=self.destroy
        )
        btn_cancelar.pack(side="left")

        self.btn_importar_lote = ctk.CTkButton(
            rodape_lote,
            text="📥 IMPORTAR SELECIONADAS (0) ➔",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#d9822b",
            hover_color="#b8691b",
            state="disabled",
            width=260,
            height=38,
            command=self._executar_importacao_lote
        )
        self.btn_importar_lote.pack(side="right")

        # Barra de Progresso (inicialmente oculta)
        self.frame_progresso = ctk.CTkFrame(self.frame_lote, fg_color="transparent")
        self.lbl_progresso = ctk.CTkLabel(self.frame_progresso, text="", font=ctk.CTkFont(size=11))
        self.lbl_progresso.pack(anchor="w")
        self.bar_progresso = ctk.CTkProgressBar(self.frame_progresso, height=12)
        self.bar_progresso.pack(fill="x", pady=(2, 6))

        # CARD 1: SELEÇÃO DA PASTA DE ORIGEM
        card_busca = ctk.CTkFrame(self.frame_lote, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        card_busca.pack(fill="x", padx=10, pady=(10, 8))

        ctk.CTkLabel(
            card_busca,
            text="Selecione a pasta onde estão suas peças desenhadas:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 4))

        linha_pasta = ctk.CTkFrame(card_busca, fg_color="transparent")
        linha_pasta.pack(fill="x", padx=15, pady=(0, 10))

        self.entry_pasta_lote = ctk.CTkEntry(
            linha_pasta,
            placeholder_text="Caminho da pasta externa com arquivos SolidWorks...",
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.entry_pasta_lote.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_proc_pasta = ctk.CTkButton(
            linha_pasta,
            text="📁 Procurar...",
            width=110,
            height=36,
            command=self._selecionar_pasta_lote
        )
        btn_proc_pasta.pack(side="left", padx=(0, 8))

        self.btn_escanear = ctk.CTkButton(
            linha_pasta,
            text="🔍 ESCANEAR PASTA",
            font=ctk.CTkFont(weight="bold"),
            width=150,
            height=36,
            command=self._executar_varredura_lote
        )
        self.btn_escanear.pack(side="right")

        # Seleção da Linha de Produto para o Lote
        frame_linha_lote = ctk.CTkFrame(self.frame_lote, fg_color="transparent")
        frame_linha_lote.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(
            frame_linha_lote,
            text="Linha de Produto para as peças deste lote:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(5, 8))

        self.combo_linha_lote = ctk.CTkComboBox(
            frame_linha_lote,
            values=LINHAS_PRODUTO,
            state="readonly",
            height=32,
            font=ctk.CTkFont(size=12),
            width=160
        )
        self.combo_linha_lote.set("MedicalFix")
        self.combo_linha_lote.pack(side="left")

        # CARD 2: RESUMO E FERRAMENTAS DE SELEÇÃO
        self.frame_resumo_lote = ctk.CTkFrame(self.frame_lote, fg_color="transparent")
        self.frame_resumo_lote.pack(fill="x", padx=10, pady=(0, 6))

        self.lbl_resumo_lote = ctk.CTkLabel(
            self.frame_resumo_lote,
            text="Selecione uma pasta e clique em 'Escanear Pasta' para listar as peças prontas.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.lbl_resumo_lote.pack(side="left")

        self.btn_marcar_todos = ctk.CTkButton(
            self.frame_resumo_lote,
            text="Marcar Todos",
            width=90,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#444444",
            hover_color="#333333",
            command=lambda: self._alterar_todas_selecoes(True)
        )
        self.btn_marcar_todos.pack(side="right", padx=(4, 0))

        self.btn_desmarcar_todos = ctk.CTkButton(
            self.frame_resumo_lote,
            text="Desmarcar Todos",
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#444444",
            hover_color="#333333",
            command=lambda: self._alterar_todas_selecoes(False)
        )
        self.btn_desmarcar_todos.pack(side="right", padx=(4, 0))

        # CARD 3: TABELA ROLÁVEL DE PEÇAS DETECTADAS
        self.scroll_tabela_lote = ctk.CTkScrollableFrame(self.frame_lote, corner_radius=10)
        self.scroll_tabela_lote.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    def _ao_alternar_modo(self, modo_selecionado: str):
        if "Individual" in modo_selecionado:
            self._mostrar_visao_individual()
        else:
            self._mostrar_visao_lote()

    def _mostrar_visao_individual(self):
        self.frame_lote.pack_forget()
        self.frame_individual.pack(fill="both", expand=True)

    def _mostrar_visao_lote(self):
        self.frame_individual.pack_forget()
        self.frame_lote.pack(fill="both", expand=True)

    def _selecionar_pasta_lote(self):
        pasta = filedialog.askdirectory(title="Selecionar Pasta com Peças SolidWorks", parent=self)
        if pasta:
            self.entry_pasta_lote.delete(0, "end")
            self.entry_pasta_lote.insert(0, os.path.normpath(pasta))
            self._executar_varredura_lote()

    def _executar_varredura_lote(self):
        pasta = self.entry_pasta_lote.get().strip()
        if not pasta or not os.path.isdir(pasta):
            messagebox.showwarning("Pasta Inválida", "Por favor, selecione uma pasta válida para escanear.", parent=self)
            return

        self.btn_escanear.configure(state="disabled", text="Escaneando...")
        self.update_idletasks()

        # Limpa tabela anterior
        for widget in self.scroll_tabela_lote.winfo_children():
            widget.destroy()
        self.widgets_linha_lote.clear()

        itens = self.storage.escanear_pasta_externa(pasta, recursivo=True)
        self.itens_lote_detectados = itens

        self.btn_escanear.configure(state="normal", text="🔍 ESCANEAR PASTA")

        if not itens:
            self.lbl_resumo_lote.configure(text="Nenhum arquivo SolidWorks (.SLDPRT, .SLDASM, .SLDDRW) foi encontrado nesta pasta.")
            self.btn_importar_lote.configure(state="disabled", text="📥 IMPORTAR SELECIONADAS (0) ➔")
            ctk.CTkLabel(
                self.scroll_tabela_lote,
                text="Nenhum arquivo SolidWorks encontrado na pasta selecionada.",
                font=ctk.CTkFont(size=13),
                text_color="gray"
            ).pack(pady=40)
            return

        total_3d = sum(1 for i in itens if i["tem_3d"])
        total_2d = sum(1 for i in itens if i["tem_2d"])
        total_cad = sum(1 for i in itens if i["ja_cadastrado"])

        self.lbl_resumo_lote.configure(
            text=f"Total: {len(itens)} itens detectados ({total_3d} com 3D, {total_2d} com 2D) | {total_cad} já no sistema."
        )

        # Cabeçalho da Tabela
        header_tab = ctk.CTkFrame(self.scroll_tabela_lote, fg_color=("#dddddd", "#282c34"), height=32, corner_radius=6)
        header_tab.pack(fill="x", pady=(0, 4), padx=2)

        ctk.CTkLabel(header_tab, text="SEL", width=36, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header_tab, text="TIPO", width=65, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header_tab, text="CÓDIGO (000.000)", width=110, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header_tab, text="NOME DA PEÇA", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=8, fill="x", expand=True)
        ctk.CTkLabel(header_tab, text="3D", width=40, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(header_tab, text="2D", width=40, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(header_tab, text="STATUS", width=110, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=6)

        # Renderiza linhas da tabela
        for item in itens:
            linha = ctk.CTkFrame(self.scroll_tabela_lote, fg_color=("#f5f5f5", "#1e2227"), height=40, corner_radius=6)
            linha.pack(fill="x", pady=2, padx=2)

            var_sel = ctk.BooleanVar(value=item["selecionado"])
            chk = ctk.CTkCheckBox(linha, text="", variable=var_sel, width=24, command=self._atualizar_contador_lote)
            chk.pack(side="left", padx=(8, 4))

            # Tipo Badge
            cor_tipo = "#1f6aa5" if item["tipo"] == "Peça" else ("#d9822b" if item["tipo"] == "CO" else "#9c27b0")
            lbl_tipo = ctk.CTkLabel(
                linha,
                text=item["tipo"][:4].upper(),
                width=55,
                height=22,
                fg_color=cor_tipo,
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=10, weight="bold")
            )
            lbl_tipo.pack(side="left", padx=4)

            # Código (Entry editável)
            entry_cod = ctk.CTkEntry(
                linha,
                width=105,
                height=30,
                font=ctk.CTkFont(size=11, family="Consolas")
            )
            if item["codigo"]:
                entry_cod.insert(0, item["codigo"])
            entry_cod.pack(side="left", padx=4)

            # Nome (Entry editável)
            entry_nome = ctk.CTkEntry(
                linha,
                height=30,
                font=ctk.CTkFont(size=12)
            )
            entry_nome.insert(0, item["nome"])
            entry_nome.pack(side="left", fill="x", expand=True, padx=6)

            # Badge 3D
            lbl_3d = ctk.CTkLabel(
                linha,
                text="3D ✓" if item["tem_3d"] else "—",
                width=38,
                text_color="#2fa572" if item["tem_3d"] else "gray",
                font=ctk.CTkFont(size=11, weight="bold" if item["tem_3d"] else "normal")
            )
            lbl_3d.pack(side="left", padx=2)

            # Badge 2D
            lbl_2d = ctk.CTkLabel(
                linha,
                text="2D ✓" if item["tem_2d"] else "—",
                width=38,
                text_color="#2fa572" if item["tem_2d"] else "gray",
                font=ctk.CTkFont(size=11, weight="bold" if item["tem_2d"] else "normal")
            )
            lbl_2d.pack(side="left", padx=2)

            # Status
            if item["ja_cadastrado"]:
                lbl_status = ctk.CTkLabel(
                    linha,
                    text="Já cadastrado",
                    width=100,
                    text_color="#e74c3c",
                    font=ctk.CTkFont(size=11, weight="bold")
                )
            elif not item["codigo"]:
                lbl_status = ctk.CTkLabel(
                    linha,
                    text="Definir código",
                    width=100,
                    text_color="#d9822b",
                    font=ctk.CTkFont(size=11)
                )
            else:
                lbl_status = ctk.CTkLabel(
                    linha,
                    text="Pronto ✓",
                    width=100,
                    text_color="#2fa572",
                    font=ctk.CTkFont(size=11, weight="bold")
                )
            lbl_status.pack(side="left", padx=6)

            self.widgets_linha_lote.append({
                "item": item,
                "var_sel": var_sel,
                "entry_cod": entry_cod,
                "entry_nome": entry_nome
            })

        self._atualizar_contador_lote()

    def _alterar_todas_selecoes(self, estado: bool):
        for w in self.widgets_linha_lote:
            if estado and w["item"]["ja_cadastrado"]:
                continue
            w["var_sel"].set(estado)
        self._atualizar_contador_lote()

    def _atualizar_contador_lote(self):
        total_selecionados = sum(1 for w in self.widgets_linha_lote if w["var_sel"].get())
        if total_selecionados > 0:
            self.btn_importar_lote.configure(
                state="normal",
                text=f"📥 IMPORTAR SELECIONADAS ({total_selecionados} PEÇAS) ➔"
            )
        else:
            self.btn_importar_lote.configure(
                state="disabled",
                text="📥 IMPORTAR SELECIONADAS (0) ➔"
            )

    def _executar_importacao_lote(self):
        itens_para_importar = [w for w in self.widgets_linha_lote if w["var_sel"].get()]
        if not itens_para_importar:
            messagebox.showwarning("Nenhuma Peça Selecionada", "Marque pelo menos uma peça para importar.", parent=self)
            return

        # 1. Validação preliminar de todos os itens marcados
        for w in itens_para_importar:
            cod = w["entry_cod"].get().strip()
            nome = w["entry_nome"].get().strip()
            tipo = w["item"]["tipo"]

            val_cod, msg_cod = validar_codigo(cod, tipo=tipo)
            if not val_cod:
                messagebox.showerror(
                    "Código Inválido no Lote",
                    f"A peça '{nome}' possui um código inválido: '{cod}'.\n\n{msg_cod}\nPor favor, corrija o código na tabela antes de importar.",
                    parent=self
                )
                w["entry_cod"].focus()
                return

            val_nome, msg_nome = validar_nome_peca(nome)
            if not val_nome:
                messagebox.showerror(
                    "Nome Inválido no Lote",
                    f"A peça com código '{cod}' possui nome inválido: '{nome}'.\n\n{msg_nome}",
                    parent=self
                )
                w["entry_nome"].focus()
                return

        resposta = messagebox.askyesno(
            "Confirmar Importação em Lote",
            f"Deseja importar {len(itens_para_importar)} projetos para a pasta do sistema?\n\n"
            f"Cada projeto receberá sua estrutura padronizada (CAD, DESENHO, PDF, HISTORICO).",
            parent=self
        )
        if not resposta:
            return

        # 2. Execução da Importação em Lote com feedback de progresso
        self.frame_progresso.pack(fill="x", side="bottom", pady=(0, 6))
        self.btn_importar_lote.configure(state="disabled", text="Importando lote...")
        self.update_idletasks()

        sucessos = 0
        falhas = []
        ultima_peca = None
        linha_lote = self.combo_linha_lote.get() if hasattr(self, "combo_linha_lote") else "MedicalFix"

        total = len(itens_para_importar)
        for idx, w in enumerate(itens_para_importar):
            cod = w["entry_cod"].get().strip()
            nome = w["entry_nome"].get().strip()
            tipo = w["item"]["tipo"]
            caminho_3d = w["item"]["caminho_3d"]
            caminho_2d = w["item"]["caminho_2d"]
            caminho_pdf = w["item"]["caminho_pdf"]

            self.lbl_progresso.configure(text=f"Importando ({idx + 1}/{total}): {cod} - {nome}...")
            self.bar_progresso.set((idx + 1) / total)
            self.update_idletasks()

            ok, peca, msg = self.storage.importar_peca_existente(
                caminho_3d=caminho_3d,
                caminho_2d=caminho_2d,
                caminho_pdf=caminho_pdf,
                codigo=cod,
                nome=nome,
                tipo=tipo,
                descricao=nome,
                revisao="A",
                copiar=True,
                linha_produto=linha_lote
            )

            if ok:
                sucessos += 1
                ultima_peca = peca
                w["var_sel"].set(False)
            else:
                falhas.append(f"• {cod} - {nome}: {msg}")

        self.frame_progresso.pack_forget()

        # 3. Relatório final
        msg_relatorio = f"✓ Importação concluída!\n\n• Sucessos: {sucessos} projetos cadastrados com sucesso."
        if falhas:
            msg_relatorio += f"\n\n⚠ Falhas ({len(falhas)}):\n" + "\n".join(falhas[:5])

        messagebox.showinfo("Resultado da Importação", msg_relatorio, parent=self.parent)

        if self.on_success and ultima_peca:
            self.on_success(ultima_peca)

        self.destroy()
