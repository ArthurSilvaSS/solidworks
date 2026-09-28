"""
Janela Principal do Controle CAD.
Reúne as funções de criação de novas peças, pesquisa em tempo real,
visualização em Galeria 3D e Tabela com miniaturas, abertura no SolidWorks,
nova revisão, auditoria de projetos e configurações gerais.
"""

import os
import sys
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

from core.models import PecaInfo, obter_usuario_atual, LINHAS_PRODUTO
from core.config import carregar_config, obter_pasta_raiz
from core.logger import registrar_log
from services.storage_service import StorageService
from services.duplicate_service import DuplicateService
from services.revision_service import RevisionService
from services.audit_service import AuditService
from services.thumbnail_service import ThumbnailService
from cad.solidworks_client import SolidWorksClient

from ui.views.new_part_modal import NewPartModal
from ui.views.new_revision_modal import NewRevisionModal
from ui.views.history_modal import HistoryModal
from ui.views.validation_view import ValidationView
from ui.views.settings_modal import SettingsModal
from ui.views.confirm_delete_modal import ConfirmDeleteModal
from ui.views.select_components_modal import SelectComponentsModal
from ui.views.manage_kits_modal import ManageKitsModal
from ui.views.kits_catalog_modal import KitsCatalogModal
from ui.views.import_parts_modal import ImportPartsModal
from services.pdf_automation_service import PdfAutomationService


class ControleCADApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações gerais da janela com alta responsividade
        self.title("Controle CAD — SolidWorks")
        self.geometry("1280x760")
        self.minsize(900, 560)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Inicia maximizado no Windows para máximo aproveitamento do espaço de trabalho
        try:
            self.after(80, lambda: self.state("zoomed"))
        except Exception:
            pass

        # Inicialização dos serviços
        self.config = carregar_config()
        self.pasta_raiz = obter_pasta_raiz()
        self.storage_service = StorageService(self.pasta_raiz)
        self.duplicate_service = DuplicateService(self.storage_service)
        self.revision_service = RevisionService(self.storage_service)
        self.audit_service = AuditService(self.pasta_raiz)
        self.thumbnail_service = ThumbnailService()
        self.sw_client = SolidWorksClient(modo_simulacao=self.config.get("modo_simulacao_sw", False))
        self.pdf_service = PdfAutomationService(self.storage_service, self.sw_client, self.config)

        # Estado da interface
        self.todas_pecas: List[PecaInfo] = []
        self.pecas_filtradas: List[PecaInfo] = []
        self.peca_selecionada: Optional[PecaInfo] = None
        self.card_selecionado_widget = None
        self.modo_visualizacao = "grade"  # "grade" (Galeria 3D) ou "tabela"
        self._colunas_grid = 4
        self._timer_resize = None
        self._timer_busca = None
        self._ultima_largura_janela: int = 0
        self._cards_grid: List[ctk.CTkFrame] = []
        self._grid_container: Optional[ctk.CTkFrame] = None
        self._cache_status_pecas: Dict[str, dict] = {}

        self._construir_ui()
        self.bind("<Delete>", self._ao_pressionar_delete)
        self.bind("<Configure>", self._ao_redimensionar_janela)
        self.carregar_pecas()
        self.after(2500, self._iniciar_monitor_auto_pdf)

    def _ao_redimensionar_janela(self, event):
        """Ajusta o grid de cards da galeria 3D dinamicamente ao redimensionar a janela com alta performance."""
        if event.widget != self:
            return
        if self.modo_visualizacao != "grade":
            return
        largura = event.width
        if abs(largura - getattr(self, "_ultima_largura_janela", 0)) < 30:
            return
        self._ultima_largura_janela = largura

        novas_colunas = max(1, min(6, (largura - 80) // 240))
        if novas_colunas != getattr(self, "_colunas_grid", 4):
            if hasattr(self, "_timer_resize") and self._timer_resize:
                self.after_cancel(self._timer_resize)
            self._timer_resize = self.after(35, lambda: self._reorganizar_grade_colunas(novas_colunas))

    def _reorganizar_grade_colunas(self, novas_colunas: int):
        """Reorganiza os cards existentes nas novas colunas instantaneamente sem recriar widgets."""
        if not hasattr(self, "_grid_container") or not self._grid_container or not self._grid_container.winfo_exists():
            return
        if not hasattr(self, "_cards_grid") or not self._cards_grid:
            return
        self._colunas_grid = novas_colunas
        for c in range(6):
            self._grid_container.grid_columnconfigure(c, weight=1 if c < novas_colunas else 0, pad=10)
        for idx, card in enumerate(self._cards_grid):
            if card.winfo_exists():
                r = idx // novas_colunas
                c = idx % novas_colunas
                card.grid(row=r, column=c, padx=6, pady=8, sticky="nsew")

    def _construir_ui(self):
        # 1. BARRA SUPERIOR (HEADER)
        top_bar = ctk.CTkFrame(self, height=65, corner_radius=0)
        top_bar.pack(fill="x", side="top")

        # Logo / Título
        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        lbl_app = ctk.CTkLabel(
            title_box,
            text="CONTROLE CAD",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_app.pack(anchor="w")

        self.lbl_pasta_atual = ctk.CTkLabel(
            title_box,
            text=f"Pasta: {self.pasta_raiz}",
            font=ctk.CTkFont(size=11, family="Consolas"),
            text_color="gray"
        )
        self.lbl_pasta_atual.pack(anchor="w")

        # Usuário e Tema à direita
        right_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_box.pack(side="right", padx=20, pady=10)

        lbl_user = ctk.CTkLabel(
            right_box,
            text=f"Projetista: {obter_usuario_atual()}",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_user.pack(side="left", padx=10)

        self.switch_tema = ctk.CTkSwitch(
            right_box,
            text="Escuro",
            command=self._alternar_tema
        )
        self.switch_tema.select()
        self.switch_tema.pack(side="left")

        # 2. BARRA DE AÇÕES RÁPIDAS (RESPONSIVA)
        actions_bar = ctk.CTkFrame(self, fg_color="transparent")
        actions_bar.pack(fill="x", padx=20, pady=(8, 6))

        # Container Esquerda (Ações de Criação e Automação)
        self.actions_left = ctk.CTkFrame(actions_bar, fg_color="transparent")
        self.actions_left.pack(side="left", fill="x", expand=True)

        # Botão Nova Peça (Destaque Principal)
        self.btn_nova_peca = ctk.CTkButton(
            self.actions_left,
            text="➕ NOVA PEÇA",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144d75",
            height=38,
            width=125,
            command=self._abrir_nova_peca
        )
        self.btn_nova_peca.pack(side="left", padx=(0, 6))

        # Botão Importar Peças Prontas (3D e 2D)
        self.btn_importar_peca = ctk.CTkButton(
            self.actions_left,
            text="📥 IMPORTAR PEÇAS",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#d9822b",
            hover_color="#b8691b",
            height=38,
            width=145,
            command=self._abrir_importar_pecas
        )
        self.btn_importar_peca.pack(side="left", padx=(0, 6))

        # Botão Nova Revisão
        self.btn_nova_revisao = ctk.CTkButton(
            self.actions_left,
            text="↻ NOVA REVISÃO",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2fa572",
            hover_color="#238257",
            height=38,
            width=130,
            command=self._abrir_nova_revisao
        )
        self.btn_nova_revisao.pack(side="left", padx=(0, 6))

        # Botão Cadastrar / Gerenciar Kits
        self.btn_cadastrar_kits = ctk.CTkButton(
            self.actions_left,
            text="🏷️ CADASTRAR KITS",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334d66",
            hover_color="#24384a",
            height=38,
            width=140,
            command=self._abrir_cadastro_kits
        )
        self.btn_cadastrar_kits.pack(side="left", padx=(0, 6))

        # Botão Sincronizar / Auto-PDF
        self.btn_sync_pdf = ctk.CTkButton(
            self.actions_left,
            text="⚡ SINCRONIZAR PDFs",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3a5a78",
            hover_color="#2b435a",
            height=38,
            width=150,
            command=self._acao_sincronizar_pdfs_manualmente
        )
        self.btn_sync_pdf.pack(side="left", padx=(0, 6))

        # Botão Validar Projetos
        self.btn_validar = ctk.CTkButton(
            self.actions_left,
            text="✓ AUDITORIA",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#d9534f",
            hover_color="#b53f3c",
            height=38,
            width=115,
            command=self._abrir_validar_projetos
        )
        self.btn_validar.pack(side="left", padx=(0, 6))

        # Container Direita (Atualizar e Configurações)
        self.actions_right = ctk.CTkFrame(actions_bar, fg_color="transparent")
        self.actions_right.pack(side="right")

        self.btn_config = ctk.CTkButton(
            self.actions_right,
            text="⚙ CONFIGURAÇÕES",
            font=ctk.CTkFont(size=11),
            fg_color="#444444",
            hover_color="#333333",
            height=38,
            width=125,
            command=self._abrir_configuracoes
        )
        self.btn_config.pack(side="right")

        self.btn_atualizar = ctk.CTkButton(
            self.actions_right,
            text="🔄 ATUALIZAR",
            font=ctk.CTkFont(size=11),
            fg_color="#444444",
            hover_color="#333333",
            height=38,
            width=105,
            command=self.carregar_pecas
        )
        self.btn_atualizar.pack(side="right", padx=(0, 6))

        # 3. BARRA DE PESQUISA E FILTROS + ALTERNADOR DE MODO (GRADE / TABELA)
        search_bar = ctk.CTkFrame(self, fg_color="transparent")
        search_bar.pack(fill="x", padx=20, pady=(5, 10))

        self.entry_busca = ctk.CTkEntry(
            search_bar,
            placeholder_text="🔎 Pesquisar por código, nome, descrição ou kit (ex: torquímetro)...",
            font=ctk.CTkFont(size=13),
            height=38
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_busca.bind("<KeyRelease>", self._ao_digitar_busca)

        # Filtro de Linha de Produto
        self.combo_linha_filtro = ctk.CTkComboBox(
            search_bar,
            values=["Todas as Linhas"] + LINHAS_PRODUTO,
            state="readonly",
            height=38,
            width=140,
            command=self._ao_mudar_filtro_linha
        )
        self.combo_linha_filtro.set("Todas as Linhas")
        self.combo_linha_filtro.pack(side="left", padx=(0, 8))

        # Filtro de tipo
        self.combo_tipo_filtro = ctk.CTkComboBox(
            search_bar,
            values=["Todos os Tipos", "Peça", "Montagem", "CO"],
            state="readonly",
            height=38,
            width=140,
            command=lambda val: self._filtrar_pecas()
        )
        self.combo_tipo_filtro.set("Todos os Tipos")
        self.combo_tipo_filtro.pack(side="left", padx=(0, 8))

        # Filtro de Kit
        self.combo_kit_filtro = ctk.CTkComboBox(
            search_bar,
            values=["Todos os Kits"],
            state="readonly",
            height=38,
            width=150,
            command=lambda val: self._filtrar_pecas()
        )
        self.combo_kit_filtro.set("Todos os Kits")
        self.combo_kit_filtro.pack(side="left", padx=(0, 10))

        # Alternador de modo de exibição (Galeria 3D / Tabela)
        self.seg_modo = ctk.CTkSegmentedButton(
            search_bar,
            values=["🎴 Galeria 3D", "📋 Tabela"],
            height=38,
            command=self._ao_trocar_modo_visualizacao
        )
        self.seg_modo.set("🎴 Galeria 3D")
        self.seg_modo.pack(side="left", padx=(0, 10))

        self.lbl_contador = ctk.CTkLabel(
            search_bar,
            text="Total: 0 peças",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.lbl_contador.pack(side="right", padx=5)

        # 4. CONTAINER PRINCIPAL (SCROLLABLE FRAME PARA CARDS OU TABELA)
        self.view_container = ctk.CTkFrame(self, corner_radius=10)
        self.view_container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Cabeçalho da Tabela (visível apenas no modo tabela)
        self.table_header = ctk.CTkFrame(self.view_container, fg_color=("#e1e1e1", "#2b2b2b"), height=36)
        
        ctk.CTkLabel(self.table_header, text="3D", width=65, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(self.table_header, text="CÓDIGO", width=95, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(self.table_header, text="NOME DA PEÇA", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(self.table_header, text="LINHA", width=85, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(self.table_header, text="REV", width=45, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(self.table_header, text="PDF", width=65, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(self.table_header, text="TIPO", width=85, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(self.table_header, text="RESPONSÁVEL", width=105, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(self.table_header, text="DATA CRIAÇÃO", width=120, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self.view_container, corner_radius=6)
        self.scroll_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._configurar_rolagem_suave()

        # 5. PAINEL DE AÇÕES E PREVIEW DA PEÇA SELECIONADA (2 NÍVEIS RESPONSIVOS)
        self.action_panel = ctk.CTkFrame(self, corner_radius=10)
        self.action_panel.pack(fill="x", padx=20, pady=(0, 15))

        # Nível 1: Banner com Miniatura 3D e Dados Completos da Peça (Largura Total)
        self.preview_box = ctk.CTkFrame(self.action_panel, fg_color="transparent")
        self.preview_box.pack(fill="x", padx=15, pady=(8, 4))

        self.lbl_thumb_sel = ctk.CTkLabel(self.preview_box, text="", width=65)
        self.lbl_thumb_sel.pack(side="left", padx=(0, 12))

        info_box = ctk.CTkFrame(self.preview_box, fg_color="transparent")
        info_box.pack(side="left", fill="x", expand=True)

        self.lbl_peca_sel = ctk.CTkLabel(
            info_box,
            text="Nenhuma peça selecionada.",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_peca_sel.pack(anchor="w")

        self.lbl_peca_detalhes = ctk.CTkLabel(
            info_box,
            text="Clique em uma peça da galeria acima para ver detalhes e abrir no CAD.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.lbl_peca_detalhes.pack(anchor="w")

        # Divisor visual sutil
        ctk.CTkFrame(self.action_panel, height=1, fg_color=("#d0d0d0", "#303640")).pack(fill="x", padx=15, pady=(2, 6))

        # Nível 2: Barra Completa de Botões de Ação (Aproveita 100% da largura da janela)
        self.btn_container = ctk.CTkFrame(self.action_panel, fg_color="transparent")
        self.btn_container.pack(fill="x", padx=15, pady=(0, 8))

        # Sub-grupo Esquerdo: Ações CAD & Desenho
        self.frame_acoes_cad = ctk.CTkFrame(self.btn_container, fg_color="transparent")
        self.frame_acoes_cad.pack(side="left")

        self.btn_abrir_cad = ctk.CTkButton(
            self.frame_acoes_cad,
            text="📐 Abrir CAD",
            width=95,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_abrir_cad
        )
        self.btn_abrir_cad.pack(side="left", padx=(0, 5))

        self.btn_abrir_desenho = ctk.CTkButton(
            self.frame_acoes_cad,
            text="📝 Desenho 2D",
            width=115,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_abrir_desenho
        )
        self.btn_abrir_desenho.pack(side="left", padx=(0, 5))

        self.btn_gerar_pdf = ctk.CTkButton(
            self.frame_acoes_cad,
            text="🖨️ Gerar PDF",
            width=95,
            height=32,
            fg_color="#1f6aa5",
            hover_color="#144d75",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_gerar_pdf
        )
        self.btn_gerar_pdf.pack(side="left", padx=(0, 5))

        self.btn_abrir_pdf = ctk.CTkButton(
            self.frame_acoes_cad,
            text="📄 Abrir PDF",
            width=90,
            height=32,
            font=ctk.CTkFont(size=11),
            command=self._acao_abrir_pdf
        )
        self.btn_abrir_pdf.pack(side="left", padx=(0, 5))

        # Sub-grupo Direito: Ações de Gestão, Kits e Pasta
        self.frame_acoes_gestao = ctk.CTkFrame(self.btn_container, fg_color="transparent")
        self.frame_acoes_gestao.pack(side="right")

        self.btn_gerenciar_kits = ctk.CTkButton(
            self.frame_acoes_gestao,
            text="🏷️ Kits",
            width=80,
            height=32,
            fg_color="#334d66",
            hover_color="#24384a",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_gerenciar_kits
        )
        self.btn_gerenciar_kits.pack(side="left", padx=(0, 5))

        self.btn_componentes = ctk.CTkButton(
            self.frame_acoes_gestao,
            text="📦 COs (Montagem)",
            width=135,
            height=32,
            fg_color="#d9822b",
            hover_color="#b8691b",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_gerenciar_componentes
        )

        self.btn_historico = ctk.CTkButton(
            self.frame_acoes_gestao,
            text="📜 Histórico",
            width=85,
            height=32,
            fg_color="#444444",
            hover_color="#333333",
            font=ctk.CTkFont(size=11),
            command=self._acao_abrir_historico
        )
        self.btn_historico.pack(side="left", padx=(0, 5))

        self.btn_abrir_pasta = ctk.CTkButton(
            self.frame_acoes_gestao,
            text="📁 Pasta",
            width=80,
            height=32,
            fg_color="#444444",
            hover_color="#333333",
            font=ctk.CTkFont(size=11),
            command=self._acao_abrir_pasta
        )
        self.btn_abrir_pasta.pack(side="left", padx=(0, 5))

        self.btn_excluir = ctk.CTkButton(
            self.frame_acoes_gestao,
            text="🗑️ Excluir",
            width=80,
            height=32,
            fg_color="#b83232",
            hover_color="#8c2323",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._acao_excluir_desenho
        )
        self.btn_excluir.pack(side="left")

        # Desabilita botões iniciais
        self._atualizar_estado_botoes_selecao(habilitado=False)

    def _configurar_rolagem_suave(self):
        """Otimiza a rolagem do mouse e da scrollbar para eliminar o arrasto de texto (ghosting) e garantir fluidez máxima."""
        canvas = self.scroll_frame._parent_canvas

        def _ao_arrastar_scrollbar(*args):
            canvas.yview(*args)
            canvas.update_idletasks()

        # Vincula redesenho imediato ao arrastar a barra de rolagem lateral
        self.scroll_frame._scrollbar.configure(command=_ao_arrastar_scrollbar)

        # Remove o handler padrão do CustomTkinter (que rola a apenas 20px e não limpa dirty rects)
        self.unbind_all("<MouseWheel>")

        def _ao_rolar_mouse(event):
            try:
                # Verifica se o cursor está dentro da área de conteúdo rolável
                if self.scroll_frame._check_if_valid_scroll(event.widget):
                    if getattr(self.scroll_frame, "_shift_pressed", False):
                        if canvas.xview() != (0.0, 1.0):
                            passo = -int(event.delta / 3) if event.delta else 0
                            canvas.xview("scroll", passo, "units")
                            canvas.update_idletasks()
                    else:
                        if canvas.yview() != (0.0, 1.0):
                            # Passo de ~46px por notch: rolagem muito mais rápida, natural e fluida
                            passo = -int(event.delta / 2.6) if event.delta else 0
                            canvas.yview("scroll", passo, "units")
                            # update_idletasks força o redesenho síncrono das posições dos widgets filhos,
                            # eliminando completamente o arrasto visual de texto e rastro/ghosting na tela.
                            canvas.update_idletasks()
            except Exception:
                pass

        self.bind_all("<MouseWheel>", _ao_rolar_mouse)

        if "linux" in sys.platform:
            def _ao_rolar_linux_up(event):
                if self.scroll_frame._check_if_valid_scroll(event.widget):
                    canvas.yview_scroll(-3, "units")
                    canvas.update_idletasks()

            def _ao_rolar_linux_down(event):
                if self.scroll_frame._check_if_valid_scroll(event.widget):
                    canvas.yview_scroll(3, "units")
                    canvas.update_idletasks()

            self.bind_all("<Button-4>", _ao_rolar_linux_up)
            self.bind_all("<Button-5>", _ao_rolar_linux_down)

    def _ao_trocar_modo_visualizacao(self, valor):
        if "Galeria" in valor:
            self.modo_visualizacao = "grade"
        else:
            self.modo_visualizacao = "tabela"
        self._renderizar_conteudo()

    def _alternar_tema(self):
        if self.switch_tema.get():
            ctk.set_appearance_mode("Dark")
            self.switch_tema.configure(text="Escuro")
        else:
            ctk.set_appearance_mode("Light")
            self.switch_tema.configure(text="Claro")

    def carregar_pecas(self):
        """Carrega e atualiza a lista de peças da pasta raiz."""
        self.todas_pecas = self.storage_service.listar_todas_pecas()
        self.thumbnail_service.limpar_cache()
        if hasattr(self, "_cache_status_pecas"):
            self._cache_status_pecas.clear()
        self._atualizar_opcoes_kits_filtro()
        self._filtrar_pecas()
        self._deselecionar_peca()
        self._verificar_e_disparar_auto_pdf()

    def _obter_status_peca(self, peca: PecaInfo, forcar_recarregar: bool = False) -> dict:
        """Obtém status de CAD, desenho e PDF com cache em memória para não travar a UI com I/O de disco."""
        if not hasattr(self, "_cache_status_pecas"):
            self._cache_status_pecas = {}

        if not forcar_recarregar and peca.codigo in self._cache_status_pecas:
            st = self._cache_status_pecas[peca.codigo]
            st["proc_pdf"] = self.pdf_service.esta_processando(peca.codigo)
            return st

        tem_cad = self.storage_service.peca_tem_cad(peca)
        tem_des = self.storage_service.peca_tem_desenho(peca)
        tem_pdf = self.storage_service.peca_tem_pdf(peca)
        precisa_att = False
        if tem_pdf:
            precisa_att, _ = self.storage_service.peca_precisa_gerar_pdf(peca)

        st = {
            "tem_cad": tem_cad,
            "tem_des": tem_des,
            "tem_pdf": tem_pdf,
            "precisa_att": precisa_att,
            "proc_pdf": self.pdf_service.esta_processando(peca.codigo)
        }
        self._cache_status_pecas[peca.codigo] = st
        return st

    def _ao_digitar_busca(self, event=None):
        """Aplica debounce na pesquisa para manter a digitação 100% fluida."""
        if hasattr(self, "_timer_busca") and self._timer_busca:
            self.after_cancel(self._timer_busca)
        self._timer_busca = self.after(120, self._filtrar_pecas)

    def _ao_mudar_filtro_linha(self, valor):
        self._atualizar_opcoes_kits_filtro()
        self._filtrar_pecas()

    def _atualizar_opcoes_kits_filtro(self):
        if not hasattr(self, "combo_kit_filtro"):
            return
        linha_sel = self.combo_linha_filtro.get() if hasattr(self, "combo_linha_filtro") else "Todas as Linhas"
        linha_arg = linha_sel if linha_sel != "Todas as Linhas" else None
        kits_cadastrados = self.storage_service.obter_todos_kits(linha=linha_arg)
        valores = ["Todos os Kits"] + kits_cadastrados
        kit_atual = self.combo_kit_filtro.get()
        self.combo_kit_filtro.configure(values=valores)
        if kit_atual in valores:
            self.combo_kit_filtro.set(kit_atual)
        else:
            self.combo_kit_filtro.set("Todos os Kits")

    def _filtrar_pecas(self):
        termo = self.entry_busca.get().strip().lower()
        tipo_filtro = self.combo_tipo_filtro.get()
        linha_filtro = getattr(self, "combo_linha_filtro", None)
        linha_selecionada = linha_filtro.get() if linha_filtro else "Todas as Linhas"
        kit_filtro = getattr(self, "combo_kit_filtro", None)
        kit_selecionado = kit_filtro.get() if kit_filtro else "Todos os Kits"

        self.pecas_filtradas = []
        for p in self.todas_pecas:
            # Filtro por tipo
            if tipo_filtro != "Todos os Tipos" and p.tipo != tipo_filtro:
                continue

            # Filtro por Linha de Produto
            if linha_selecionada != "Todas as Linhas":
                p_linha = getattr(p, "linha_produto", "MedicalFix") or "MedicalFix"
                if p_linha.lower() != linha_selecionada.lower():
                    continue

            # Filtro por kit selecionado no dropdown
            if kit_selecionado != "Todos os Kits":
                if not any(k.lower() == kit_selecionado.lower() for k in p.kits):
                    continue

            # Filtro por busca textual (código, nome, descrição, linha ou qualquer kit vinculado)
            if termo:
                bateu_codigo = termo in p.codigo.lower()
                bateu_nome = termo in p.nome.lower()
                bateu_desc = termo in p.descricao.lower()
                bateu_kits = any(termo in k.lower() for k in p.kits)
                p_linha = getattr(p, "linha_produto", "") or ""
                bateu_linha = termo in p_linha.lower()

                if not (bateu_codigo or bateu_nome or bateu_desc or bateu_kits or bateu_linha):
                    continue

            self.pecas_filtradas.append(p)

        self.lbl_contador.configure(text=f"Total: {len(self.pecas_filtradas)} de {len(self.todas_pecas)} peças")
        self._renderizar_conteudo()

    def _renderizar_conteudo(self):
        # Limpa widgets anteriores
        self._cards_grid = []
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if self.modo_visualizacao == "grade":
            self.table_header.pack_forget()
            self._renderizar_grade_3d()
        else:
            self.table_header.pack(fill="x", padx=6, pady=(6, 2), before=self.scroll_frame)
            self._renderizar_tabela_3d()

    def _renderizar_grade_3d(self):
        """Renderiza a Galeria 3D com Cards Visuais das Peças."""
        if not self.pecas_filtradas:
            msg = "Nenhuma peça encontrada." if self.todas_pecas else "Nenhuma peça cadastrada. Clique em '+ NOVA PEÇA' para começar."
            ctk.CTkLabel(self.scroll_frame, text=msg, text_color="gray", font=ctk.CTkFont(size=14)).pack(pady=50)
            return

        # Grid container responsivo com cálculo dinâmico de colunas
        grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, padx=8, pady=8)
        self._grid_container = grid_container
        self._cards_grid = []

        # Detecta largura real disponível para distribuir colunas de ~240px
        largura = self.scroll_frame.winfo_width()
        if largura <= 50:
            largura = max(800, self.winfo_width() - 80)
        num_colunas = max(1, min(6, largura // 240))
        self._colunas_grid = num_colunas

        for c in range(num_colunas):
            grid_container.grid_columnconfigure(c, weight=1, pad=10)

        for idx, peca in enumerate(self.pecas_filtradas):
            row_idx = idx // num_colunas
            col_idx = idx % num_colunas

            # Card da Peça
            is_selected = (self.peca_selecionada and self.peca_selecionada.codigo == peca.codigo)
            border_color = "#1f6aa5" if is_selected else ("#d0d0d0", "#333842")
            border_width = 2 if is_selected else 1
            bg_card = ("#f4f5f7", "#1e2228") if not is_selected else ("#e3f0fc", "#1a324a")

            card = ctk.CTkFrame(
                grid_container,
                corner_radius=10,
                fg_color=bg_card,
                border_width=border_width,
                border_color=border_color
            )
            card.grid(row=row_idx, column=col_idx, padx=6, pady=8, sticky="nsew")
            self._cards_grid.append(card)

            if is_selected:
                self.card_selecionado_widget = card

            # Bindings de clique e duplo clique
            def bind_all_children(widget, p=peca, c=card):
                widget.bind("<Button-1>", lambda event: self._selecionar_peca(p, c))
                widget.bind("<Double-Button-1>", lambda event: self._acao_abrir_cad())
                widget.bind("<Button-3>", lambda event: self._mostrar_menu_contexto(event, p, c))
                for child in widget.winfo_children():
                    bind_all_children(child, p, c)

            # Topo do Card: Código e Badges
            top_frame = ctk.CTkFrame(card, fg_color=bg_card, corner_radius=0)
            top_frame.pack(fill="x", padx=10, pady=(10, 4))

            lbl_cod = ctk.CTkLabel(
                top_frame,
                text=peca.codigo,
                fg_color=bg_card,
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold")
            )
            lbl_cod.pack(side="left")

            rev_badge = ctk.CTkLabel(
                top_frame,
                text=f"Rev {peca.revisao_atual}",
                fg_color="#2fa572",
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=45,
                height=20
            )
            rev_badge.pack(side="right")

            # Badge do status do PDF (via cache em memória)
            status_p = self._obter_status_peca(peca)
            tem_cad = status_p["tem_cad"]
            tem_des = status_p["tem_des"]
            tem_pdf = status_p["tem_pdf"]
            proc_pdf = status_p["proc_pdf"]
            precisa_att = status_p["precisa_att"]

            if tem_pdf:
                if precisa_att:
                    txt_pdf, cor_pdf = "PDF ⚡", "#d9822b"
                else:
                    txt_pdf, cor_pdf = "PDF ✓", "#2fa572"
            elif tem_cad and tem_des:
                txt_pdf, cor_pdf = ("PDF ⏳", "#1f6aa5") if proc_pdf else ("PDF ⚡", "#e67e22")
            else:
                txt_pdf, cor_pdf = "Sem Des.", "#444444"

            badge_pdf = ctk.CTkLabel(
                top_frame,
                text=txt_pdf,
                fg_color=cor_pdf,
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=10, weight="bold"),
                width=52,
                height=20
            )
            badge_pdf.pack(side="right", padx=(0, 5))

            # Imagem 3D da Peça no Centro
            img_ctk = self.thumbnail_service.obter_ctk_image(peca, size=(190, 110))
            lbl_img = ctk.CTkLabel(card, image=img_ctk, text="", corner_radius=6, fg_color=bg_card)
            lbl_img.pack(padx=10, pady=(4, 8))

            # Nome da Peça
            lbl_nome = ctk.CTkLabel(
                card,
                text=peca.nome,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                fg_color=bg_card
            )
            lbl_nome.pack(fill="x", padx=10, pady=(0, 2))

            # Kits vinculados (exibição em destaque para saber de quais kits faz parte)
            if peca.kits:
                texto_kits = "🏷️ " + ", ".join(peca.kits[:2])
                if len(peca.kits) > 2:
                    texto_kits += f" +{len(peca.kits) - 2}"
                lbl_kits = ctk.CTkLabel(
                    card,
                    text=texto_kits,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=("#124d85", "#79b8f5"),
                    anchor="w",
                    fg_color=bg_card
                )
                lbl_kits.pack(fill="x", padx=10, pady=(0, 2))

            # Rodapé do Card: Tipo, Linha e Responsável
            footer = ctk.CTkFrame(card, fg_color=bg_card, corner_radius=0)
            footer.pack(fill="x", padx=10, pady=(2, 10))

            linha_prod = getattr(peca, "linha_produto", "MedicalFix") or "MedicalFix"
            lbl_tipo_badge = ctk.CTkLabel(
                footer,
                text=f"{peca.tipo} • {linha_prod}",
                fg_color=bg_card,
                font=ctk.CTkFont(size=10, weight="bold" if peca.tipo == "CO" else "normal"),
                text_color=("#c25e00", "#f39c12") if peca.tipo == "CO" else ("#1f6aa5", "#64b5f6")
            )
            lbl_tipo_badge.pack(side="left")

            lbl_autor = ctk.CTkLabel(
                footer,
                text=peca.criado_por,
                fg_color=bg_card,
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            lbl_autor.pack(side="right")

            # Aplica binding recursivo
            bind_all_children(card, peca, card)

    def _renderizar_tabela_3d(self):
        """Renderiza a Tabela tradicional agora enriquecida com Miniaturas 3D."""
        if not self.pecas_filtradas:
            msg = "Nenhuma peça encontrada." if self.todas_pecas else "Nenhuma peça cadastrada. Clique em '+ NOVA PEÇA' para começar."
            ctk.CTkLabel(self.scroll_frame, text=msg, text_color="gray").pack(pady=40)
            return

        for idx, peca in enumerate(self.pecas_filtradas):
            is_selected = (self.peca_selecionada and self.peca_selecionada.codigo == peca.codigo)
            if is_selected:
                bg_color = ("#cce5ff", "#1f3b5c")
            else:
                bg_color = ("#f7f7f7", "#222222") if idx % 2 == 0 else ("#ededed", "#1b1b1b")

            row = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color, height=48, corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)

            if is_selected:
                self.card_selecionado_widget = row

            def bind_row(widget, p=peca, r=row):
                widget.bind("<Button-1>", lambda event: self._selecionar_peca(p, r))
                widget.bind("<Double-Button-1>", lambda event: self._acao_abrir_cad())
                widget.bind("<Button-3>", lambda event: self._mostrar_menu_contexto(event, p, r))
                for child in widget.winfo_children():
                    bind_row(child, p, r)

            # Coluna 3D (Miniatura)
            img_thumb = self.thumbnail_service.obter_ctk_image(peca, size=(50, 36))
            lbl_thumb = ctk.CTkLabel(row, image=img_thumb, text="", width=65, fg_color=bg_color)
            lbl_thumb.pack(side="left", padx=5, pady=4)

            # Coluna Código
            lbl_cod = ctk.CTkLabel(
                row,
                text=peca.codigo,
                width=95,
                font=ctk.CTkFont(family="Consolas", weight="bold"),
                anchor="w",
                fg_color=bg_color
            )
            lbl_cod.pack(side="left", padx=5)

            # Coluna Nome (com kits destacados se houver)
            nome_exibicao = peca.nome
            if peca.kits:
                nome_exibicao += f"  🏷️ [{', '.join(peca.kits)}]"

            lbl_nome = ctk.CTkLabel(
                row,
                text=nome_exibicao,
                font=ctk.CTkFont(weight="bold"),
                anchor="w",
                fg_color=bg_color
            )
            lbl_nome.pack(side="left", padx=10, fill="x", expand=True)

            # Coluna Linha de Produto
            linha_prod = getattr(peca, "linha_produto", "MedicalFix") or "MedicalFix"
            lbl_linha_col = ctk.CTkLabel(
                row,
                text=linha_prod,
                width=85,
                fg_color=("#dfe7ef", "#2a3441"),
                text_color=("#1f6aa5", "#64b5f6"),
                corner_radius=4,
                font=ctk.CTkFont(size=10, weight="bold")
            )
            lbl_linha_col.pack(side="left", padx=4)

            # Coluna Revisão
            rev_badge = ctk.CTkLabel(
                row,
                text=peca.revisao_atual,
                width=45,
                fg_color="#2fa572",
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(weight="bold")
            )
            rev_badge.pack(side="left", padx=4)

            # Coluna PDF (via cache em memória)
            status_p = self._obter_status_peca(peca)
            tem_cad = status_p["tem_cad"]
            tem_des = status_p["tem_des"]
            tem_pdf = status_p["tem_pdf"]
            proc = status_p["proc_pdf"]
            precisa_att = status_p["precisa_att"]

            if tem_pdf:
                txt_p, cor_p = ("PDF ⚡", "#d9822b") if precisa_att else ("PDF ✓", "#2fa572")
            elif tem_cad and tem_des:
                txt_p, cor_p = ("PDF ⏳", "#1f6aa5") if proc else ("PDF ⚡", "#e67e22")
            else:
                txt_p, cor_p = "-", "#444444"

            lbl_pdf_col = ctk.CTkLabel(
                row,
                text=txt_p,
                width=65,
                fg_color=cor_p,
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=11, weight="bold")
            )
            lbl_pdf_col.pack(side="left", padx=4)

            # Coluna Tipo
            lbl_tipo = ctk.CTkLabel(row, text=peca.tipo, width=90, anchor="w", fg_color=bg_color)
            lbl_tipo.pack(side="left", padx=5)

            # Coluna Responsável
            lbl_resp = ctk.CTkLabel(row, text=peca.criado_por, width=110, anchor="w", fg_color=bg_color)
            lbl_resp.pack(side="left", padx=5)

            # Coluna Data
            lbl_data = ctk.CTkLabel(row, text=peca.criado_em, width=125, anchor="w", fg_color=bg_color)
            lbl_data.pack(side="left", padx=5)

            bind_row(row, peca, row)

    def _selecionar_peca(self, peca: PecaInfo, widget):
        # Restaura estilo do widget anterior
        if self.card_selecionado_widget and self.card_selecionado_widget.winfo_exists():
            if self.modo_visualizacao == "grade":
                self.card_selecionado_widget.configure(
                    fg_color=("#f4f5f7", "#1e2228"),
                    border_color=("#d0d0d0", "#333842"),
                    border_width=1
                )
            else:
                self.card_selecionado_widget.configure(fg_color=("#ededed", "#1b1b1b"))

        self.peca_selecionada = peca
        self.card_selecionado_widget = widget

        # Aplica destaque no widget selecionado
        if self.modo_visualizacao == "grade":
            widget.configure(
                fg_color=("#e3f0fc", "#1a324a"),
                border_color="#1f6aa5",
                border_width=2
            )
        else:
            widget.configure(fg_color=("#cce5ff", "#1f3b5c"))

        # Atualiza o Painel Inferior com a Miniatura 3D e Informações
        img_sel = self.thumbnail_service.obter_ctk_image(peca, size=(90, 58))
        self.lbl_thumb_sel.configure(image=img_sel)

        self.lbl_peca_sel.configure(
            text=f"{peca.codigo} - {peca.nome}  [Rev {peca.revisao_atual}]"
        )
        tem_pdf = self.storage_service.peca_tem_pdf(peca)
        precisa_pdf, motivo_pdf = self.storage_service.peca_precisa_gerar_pdf(peca)
        proc = self.pdf_service.esta_processando(peca.codigo)

        if proc:
            status_pdf = "⏳ Gerando PDF automaticamente..."
        elif tem_pdf and not precisa_pdf:
            status_pdf = "✓ PDF atualizado"
        elif precisa_pdf:
            status_pdf = f"⚡ {motivo_pdf}"
        else:
            status_pdf = "Sem folha de desenho para PDF"

        info_comp = ""
        if peca.tipo.upper() == "MONTAGEM":
            qtd_cos = len(peca.componentes)
            if qtd_cos > 0:
                amostra = ", ".join([f"{c.codigo} (x{c.quantidade})" for c in peca.componentes[:3]])
                if qtd_cos > 3:
                    amostra += f" +{qtd_cos - 3}"
                info_comp = f" | 📦 {qtd_cos} CO(s): {amostra}"
            else:
                info_comp = " | 📦 Sem COs vinculados"

        info_kits = ""
        if peca.kits:
            info_kits = f" | 🏷️ Kits ({len(peca.kits)}): {', '.join(peca.kits)}"
        else:
            info_kits = " | 🏷️ Sem kits"

        linha_prod = getattr(peca, "linha_produto", "MedicalFix") or "MedicalFix"
        self.lbl_peca_detalhes.configure(
            text=f"Linha: {linha_prod} | Tipo: {peca.tipo}{info_comp}{info_kits} | Criado por: {peca.criado_por} em {peca.criado_em} | PDF: {status_pdf}"
        )
        self._atualizar_estado_botoes_selecao(habilitado=True)

    def _deselecionar_peca(self):
        self.peca_selecionada = None
        self.card_selecionado_widget = None
        self.lbl_thumb_sel.configure(image="")
        self.lbl_peca_sel.configure(text="Nenhuma peça selecionada.")
        self.lbl_peca_detalhes.configure(text="Clique em uma peça da galeria acima para ver detalhes e abrir no CAD.")
        self.btn_componentes.pack_forget()
        self._atualizar_estado_botoes_selecao(habilitado=False)

    def _atualizar_estado_botoes_selecao(self, habilitado: bool):
        estado = "normal" if habilitado else "disabled"
        self.btn_abrir_cad.configure(state=estado)
        self.btn_abrir_desenho.configure(state=estado)
        
        # O botão abrir PDF só fica normal se o arquivo PDF de fato existir no disco
        if habilitado and self.peca_selecionada and self.storage_service.peca_tem_pdf(self.peca_selecionada):
            self.btn_abrir_pdf.configure(state="normal")
        else:
            self.btn_abrir_pdf.configure(state="disabled")

        self.btn_abrir_pasta.configure(state=estado)
        self.btn_historico.configure(state=estado)
        self.btn_gerenciar_kits.configure(state=estado)

        # O botão gerar PDF só fica normal se o desenho existir
        if habilitado and self.peca_selecionada and self.storage_service.peca_tem_desenho(self.peca_selecionada):
            self.btn_gerar_pdf.configure(state="normal")
        else:
            self.btn_gerar_pdf.configure(state="disabled")

        # Botão de componentes (CO) exibido apenas quando a peça selecionada for Montagem
        if habilitado and self.peca_selecionada and self.peca_selecionada.tipo.upper() == "MONTAGEM":
            self.btn_componentes.pack(side="left", padx=(0, 5), before=self.btn_historico)
            self.btn_componentes.configure(state="normal")
        else:
            self.btn_componentes.pack_forget()

        self.btn_excluir.configure(state=estado)

    # ------------------ EVENTOS DE AÇÃO ------------------

    def _abrir_nova_peca(self):
        modal = NewPartModal(
            parent=self,
            storage_service=self.storage_service,
            duplicate_service=self.duplicate_service,
            sw_client=self.sw_client,
            on_success_callback=lambda p: self.carregar_pecas()
        )

    def _abrir_importar_pecas(self):
        """Abre o modal para importação de peças prontas (3D e 2D) avulsas ou em lote."""
        modal = ImportPartsModal(
            parent=self,
            storage_service=self.storage_service,
            on_success_callback=lambda p: self.carregar_pecas(),
            sw_client=self.sw_client,
            pdf_service=self.pdf_service
        )

    def _abrir_nova_revisao(self):
        if not self.peca_selecionada:
            messagebox.showinfo("Aviso", "Por favor, selecione primeiro uma peça na lista para criar uma nova revisão.")
            return

        modal = NewRevisionModal(
            parent=self,
            peca=self.peca_selecionada,
            revision_service=self.revision_service,
            storage_service=self.storage_service,
            sw_client=self.sw_client,
            on_success_callback=lambda p: self.carregar_pecas()
        )

    def _abrir_cadastro_kits(self):
        """Abre o catálogo global de kits para cadastrar, editar e gerenciar associações de kits."""
        KitsCatalogModal(
            parent=self,
            storage_service=self.storage_service,
            thumbnail_service=self.thumbnail_service,
            on_change_callback=self.carregar_pecas
        )

    def _abrir_validar_projetos(self):
        modal = ValidationView(parent=self, audit_service=self.audit_service)

    def _abrir_configuracoes(self):
        modal = SettingsModal(
            parent=self,
            sw_client=self.sw_client,
            on_save_callback=self._ao_salvar_configuracoes
        )

    def _ao_salvar_configuracoes(self, novas_configs):
        self.config = novas_configs
        self.pasta_raiz = novas_configs["pasta_raiz"]
        self.lbl_pasta_atual.configure(text=f"Pasta: {self.pasta_raiz}")
        self.storage_service.pasta_raiz = self.pasta_raiz
        self.audit_service.pasta_raiz = self.pasta_raiz
        self.pdf_service.config = novas_configs
        self.carregar_pecas()

    def _acao_abrir_cad(self):
        if not self.peca_selecionada:
            return
        caminho_cad = self.storage_service.obter_caminho_cad(self.peca_selecionada)
        if not caminho_cad or not os.path.exists(caminho_cad):
            criar = messagebox.askyesno(
                "Arquivo CAD não encontrado",
                f"O arquivo CAD da peça '{self.peca_selecionada.codigo}' ainda não foi criado.\n\n"
                f"Deseja criar e abrir o modelo configurado no SolidWorks agora?",
                parent=self
            )
            if criar:
                ext = ".SLDASM" if self.peca_selecionada.tipo == "Montagem" else ".SLDPRT"
                pasta_cad = os.path.join(self.peca_selecionada.pasta_path, "CAD")
                caminho_novo_cad = os.path.join(pasta_cad, f"{self.peca_selecionada.codigo}{ext}")
                ok_sw, msg_sw = self.sw_client.criar_novo_documento_cad(
                    codigo=self.peca_selecionada.codigo,
                    nome=self.peca_selecionada.nome,
                    tipo=self.peca_selecionada.tipo,
                    caminho_salvar=caminho_novo_cad
                )
                if not ok_sw:
                    messagebox.showerror("Erro SolidWorks", msg_sw, parent=self)
                else:
                    messagebox.showinfo("SolidWorks", msg_sw, parent=self)
            return

        ok, msg = self.sw_client.abrir_documento(caminho_cad)
        if not ok:
            messagebox.showerror("Erro ao abrir SolidWorks", msg, parent=self)

    def _acao_abrir_desenho(self):
        if not self.peca_selecionada:
            return
        caminho_des = self.storage_service.obter_caminho_desenho(self.peca_selecionada)
        if not caminho_des or not os.path.exists(caminho_des):
            criar = messagebox.askyesno(
                "Desenho não encontrado",
                f"O arquivo de desenho 2D ({self.peca_selecionada.codigo}.SLDDRW) ainda não existe na pasta DESENHO.\n\n"
                f"Deseja criar o desenho padrão no SolidWorks agora?",
                parent=self
            )
            if criar:
                pasta_des = os.path.join(self.peca_selecionada.pasta_path, "DESENHO")
                caminho_novo_des = os.path.join(pasta_des, f"{self.peca_selecionada.codigo}.SLDDRW")
                caminho_cad = self.storage_service.obter_caminho_cad(self.peca_selecionada)

                ok_sw, msg_sw = self.sw_client.criar_novo_desenho_cad(
                    codigo=self.peca_selecionada.codigo,
                    nome=self.peca_selecionada.nome,
                    tipo=self.peca_selecionada.tipo,
                    caminho_salvar_desenho=caminho_novo_des,
                    caminho_modelo_cad=caminho_cad or ""
                )
                if not ok_sw:
                    messagebox.showerror("Erro SolidWorks", msg_sw, parent=self)
                else:
                    msg_sucesso = msg_sw
                    if self.config.get("criar_pdf", True):
                        caminho_novo_pdf = os.path.join(self.peca_selecionada.pasta_path, "PDF", f"{self.peca_selecionada.codigo}.pdf")
                        ok_pdf, _ = self.sw_client.gerar_pdf_de_desenho(caminho_novo_des, caminho_novo_pdf)
                        if ok_pdf:
                            msg_sucesso += "\n\n✓ O arquivo PDF foi gerado automaticamente na pasta PDF!"
                    messagebox.showinfo("SolidWorks", msg_sucesso, parent=self)
                    self.carregar_pecas()
            return

        ok, msg = self.sw_client.abrir_documento(caminho_des)
        if not ok:
            messagebox.showerror("Erro ao abrir SolidWorks", msg, parent=self)

    def _acao_abrir_pdf(self):
        if not self.peca_selecionada:
            return
        caminho_pdf = self.storage_service.obter_caminho_pdf(self.peca_selecionada)
        if not caminho_pdf or not os.path.exists(caminho_pdf):
            messagebox.showwarning(
                "PDF não encontrado",
                f"O arquivo {self.peca_selecionada.codigo}.pdf ainda não foi gerado na pasta PDF.\n\n"
                f"Utilize o botão '🖨️ Gerar PDF' para exportá-lo a partir do desenho."
            )
            return
        try:
            os.startfile(caminho_pdf)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o PDF: {e}")

    def _acao_abrir_pasta(self):
        if not self.peca_selecionada:
            return
        if os.path.exists(self.peca_selecionada.pasta_path):
            os.startfile(self.peca_selecionada.pasta_path)
        else:
            messagebox.showerror("Erro", "A pasta do projeto não foi encontrada no disco.")

    def _acao_abrir_historico(self):
        if not self.peca_selecionada:
            return
        modal = HistoryModal(parent=self, peca=self.peca_selecionada)

    def _acao_gerar_pdf(self):
        if not self.peca_selecionada:
            return
        caminho_des = self.storage_service.obter_caminho_desenho(self.peca_selecionada)
        if not caminho_des or not os.path.exists(caminho_des):
            messagebox.showwarning(
                "Desenho Ausente",
                f"Para gerar o PDF, o arquivo de desenho {self.peca_selecionada.codigo}.SLDDRW precisa existir na pasta DESENHO.\n\n"
                f"Clique no botão '📝 Criar / Abrir Desenho' para criá-lo primeiro.",
                parent=self
            )
            return

        caminho_pdf_destino = os.path.join(
            self.peca_selecionada.pasta_path, "PDF", f"{self.peca_selecionada.codigo}.pdf"
        )

        ok, msg = self.sw_client.gerar_pdf_de_desenho(caminho_des, caminho_pdf_destino)
        if ok:
            abrir_pdf = messagebox.askyesno(
                "PDF Gerado com Sucesso",
                f"✓ PDF exportado com sucesso!\n\nLocal: {caminho_pdf_destino}\n\nDeseja abrir o arquivo PDF agora?",
                parent=self
            )
            if abrir_pdf:
                try:
                    os.startfile(caminho_pdf_destino)
                except Exception:
                    pass
        else:
            messagebox.showerror("Erro ao Gerar PDF", msg, parent=self)

    def _acao_gerenciar_componentes(self):
        if not self.peca_selecionada or self.peca_selecionada.tipo.upper() != "MONTAGEM":
            return

        def _ao_confirmar(novos_componentes):
            self.peca_selecionada.componentes = novos_componentes
            self.storage_service.salvar_controle_json(self.peca_selecionada)
            self._selecionar_peca(self.peca_selecionada, self.card_selecionado_widget)
            messagebox.showinfo(
                "Componentes Atualizados",
                f"✓ Lista de componentes da montagem '{self.peca_selecionada.codigo}' atualizada com sucesso!\n\n"
                f"Total: {len(novos_componentes)} CO(s) vinculados.",
                parent=self
            )

        SelectComponentsModal(
            parent=self,
            storage_service=self.storage_service,
            on_confirm_callback=_ao_confirmar,
            componentes_iniciais=self.peca_selecionada.componentes,
            codigo_montagem=self.peca_selecionada.codigo,
            nome_montagem=self.peca_selecionada.nome
        )

    def _acao_gerenciar_kits(self):
        """Abre o modal para visualizar, vincular ou desvincular kits da peça ou montagem selecionada."""
        if not self.peca_selecionada:
            return

        def _ao_atualizar(peca_atualizada: PecaInfo):
            self.peca_selecionada = peca_atualizada
            self._atualizar_opcoes_kits_filtro()
            self._selecionar_peca(peca_atualizada, self.card_selecionado_widget)
            self._filtrar_pecas()

        ManageKitsModal(
            parent=self,
            peca=self.peca_selecionada,
            storage_service=self.storage_service,
            on_success_callback=_ao_atualizar
        )

    def _mostrar_menu_contexto(self, event, peca: PecaInfo, widget):
        """Exibe menu de contexto de ações rápidas com botão direito."""
        self._selecionar_peca(peca, widget)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="📐 Abrir CAD no SolidWorks", command=self._acao_abrir_cad)
        menu.add_command(label="📝 Criar / Abrir Desenho 2D", command=self._acao_abrir_desenho)
        if peca.tipo.upper() == "MONTAGEM":
            menu.add_command(label="📦 Ver / Editar Componentes (CO)...", command=self._acao_gerenciar_componentes)
        menu.add_command(label="🏷️ Gerenciar Kits Deste Item...", command=self._acao_gerenciar_kits)
        menu.add_command(label="🖨️ Gerar Arquivo PDF", command=self._acao_gerar_pdf)
        menu.add_command(label="📄 Abrir PDF Existente", command=self._acao_abrir_pdf)
        menu.add_separator()
        menu.add_command(label="📁 Abrir Pasta no Windows Explorer", command=self._acao_abrir_pasta)
        menu.add_command(label="📜 Ver Histórico de Revisões", command=self._acao_abrir_historico)
        menu.add_separator()
        menu.add_command(label="🗑️ Excluir Desenho e Todas as Pastas...", command=self._acao_excluir_desenho)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _ao_pressionar_delete(self, event=None):
        """Atalho de teclado: Delete aciona exclusão caso um desenho esteja selecionado."""
        foco = self.focus_get()
        if foco and ("entry" in str(foco).lower() or "text" in str(foco).lower()):
            return
        if self.peca_selecionada:
            self._acao_excluir_desenho()

    def _acao_excluir_desenho(self):
        """Abre modal para confirmar e executar a exclusão de todas as pastas do desenho."""
        if not self.peca_selecionada:
            messagebox.showinfo(
                "Aviso",
                "Por favor, selecione primeiro um desenho na lista para excluí-lo.",
                parent=self
            )
            return

        ConfirmDeleteModal(
            parent=self,
            peca=self.peca_selecionada,
            storage_service=self.storage_service,
            sw_client=self.sw_client,
            on_success_callback=self._ao_desenho_excluido
        )

    def _ao_desenho_excluido(self, peca_excluida: PecaInfo):
        """Callback acionado quando a exclusão for concluída com êxito."""
        self.thumbnail_service.limpar_cache(peca_excluida)
        self.carregar_pecas()

    # ------------------ AUTOMAÇÃO DE PDF ------------------

    def _verificar_e_disparar_auto_pdf(self):
        """
        Detecta projetos que já possuem CAD e Desenho 2D, mas cujo PDF
        está ausente ou desatualizado, e dispara a geração automática em segundo plano.
        """
        if not self.config.get("criar_pdf", True):
            return

        pendentes = self.pdf_service.obter_pecas_com_pdf_pendente()
        if not pendentes:
            return

        for peca, _ in pendentes:
            if not self.pdf_service.esta_processando(peca.codigo):
                self.pdf_service.gerar_pdf_async(
                    peca,
                    on_success=lambda p: self.after(0, lambda: self._ao_concluir_auto_pdf(p, True)),
                    on_error=lambda p, err: self.after(0, lambda: self._ao_concluir_auto_pdf(p, False, err))
                )

    def _ao_concluir_auto_pdf(self, peca: PecaInfo, sucesso: bool, erro: str = ""):
        """Callback executado ao concluir a exportação de um PDF em segundo plano."""
        if hasattr(self, "_cache_status_pecas"):
            self._cache_status_pecas.pop(peca.codigo, None)

        if sucesso:
            if self.peca_selecionada and self.peca_selecionada.codigo == peca.codigo:
                self.btn_abrir_pdf.configure(state="normal")
                self.lbl_peca_detalhes.configure(
                    text=f"Tipo: {peca.tipo} | Criado por: {peca.criado_por} em {peca.criado_em} | PDF: ✓ Atualizado automaticamente"
                )
            self._renderizar_conteudo()

    def _iniciar_monitor_auto_pdf(self):
        """Ciclo periódico para verificar e gerar PDFs automaticamente de projetos com CAD e Desenho."""
        try:
            if self.config.get("monitorar_pasta", True) and self.config.get("criar_pdf", True):
                self._verificar_e_disparar_auto_pdf()
        except Exception:
            pass
        finally:
            self.after(30000, self._iniciar_monitor_auto_pdf)

    def _acao_sincronizar_pdfs_manualmente(self):
        """Dispara a sincronização e geração imediata de todos os PDFs pendentes."""
        pendentes = self.pdf_service.obter_pecas_com_pdf_pendente()
        if not pendentes:
            messagebox.showinfo(
                "PDFs em Dia",
                "✓ Todos os projetos com CAD e Desenho 2D já estão com seus PDFs gerados e atualizados!",
                parent=self
            )
            return

        total = len(pendentes)
        self.btn_sync_pdf.configure(text=f"Gerando (0/{total})...", state="disabled")

        def _on_progresso(peca_concluida):
            self.after(0, lambda: self._ao_concluir_auto_pdf(peca_concluida, True))

        def _on_fim(sucessos, total_proc):
            def _atualizar_ui_fim():
                self.btn_sync_pdf.configure(text="⚡ SINCRONIZAR PDFs", state="normal")
                self.carregar_pecas()
                messagebox.showinfo(
                    "Sincronização de PDFs",
                    f"✓ Processamento finalizado!\n\n{sucessos} de {total_proc} PDFs gerados com sucesso.",
                    parent=self
                )
            self.after(0, _atualizar_ui_fim)

        self.pdf_service.processar_pendencias_em_background(
            on_peca_concluida=_on_progresso,
            on_tudo_concluido=_on_fim
        )

