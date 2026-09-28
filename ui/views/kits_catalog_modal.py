"""
Modal para Cadastro e Gerenciamento Global de Kits no Controle CAD.
Permite criar novos kits, visualizar peças vinculadas, adicionar/remover itens e renomear/excluir kits.
"""

import os
import customtkinter as ctk
from tkinter import messagebox
from typing import List, Callable, Optional, Dict, Any
from core.models import PecaInfo, LINHAS_PRODUTO
from services.storage_service import StorageService
from services.thumbnail_service import ThumbnailService
from core.logger import registrar_log


class KitsCatalogModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        storage_service: StorageService,
        thumbnail_service: ThumbnailService,
        on_change_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.parent = parent
        self.storage = storage_service
        self.thumbnail = thumbnail_service
        self.on_change = on_change_callback

        self.kit_selecionado: Optional[Dict[str, Any]] = None
        self.modo_novo_kit = True  # Começa na tela de criação ou seleção
        self.kits_cadastrados: List[Dict[str, Any]] = []
        self.todas_pecas: List[PecaInfo] = []

        self.title("Catálogo e Cadastro de Kits")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(sw - 60, 960)
        h = min(sh - 80, 650)
        self.geometry(f"{w}x{h}")
        self.minsize(740, 460)
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._construir_ui()
        self._carregar_dados()

    def _construir_ui(self):
        # 1. Cabeçalho
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", side="top", padx=25, pady=(15, 6))

        lbl_tit = ctk.CTkLabel(
            header,
            text="🏷️ CADASTRO E GERENCIAMENTO DE KITS",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        lbl_tit.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            header,
            text="Cadastre novos kits para a empresa e gerencie quais peças e montagens fazem parte de cada conjunto.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        lbl_desc.pack(anchor="w")

        # 2. Rodapé Fixo (Garante visibilidade contínua do botão fechar)
        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", padx=25, pady=(6, 12))

        btn_fechar = ctk.CTkButton(
            rodape,
            text="FECHAR",
            width=120,
            height=36,
            fg_color="#444444",
            hover_color="#333333",
            command=self.destroy
        )
        btn_fechar.pack(side="right")

        # 3. Corpo Dividido em 2 Colunas (Expande no espaço central)
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=20, pady=(5, 5))

        # --- COLUNA ESQUERDA: LISTA DE KITS ---
        col_esquerda = ctk.CTkFrame(corpo, width=310, corner_radius=10)
        col_esquerda.pack(side="left", fill="y", padx=(0, 10), pady=0)
        col_esquerda.pack_propagate(False)

        # Botão + NOVO KIT
        btn_novo = ctk.CTkButton(
            col_esquerda,
            text="➕ NOVO KIT",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144d75",
            height=38,
            command=self._iniciar_modo_novo_kit
        )
        btn_novo.pack(fill="x", padx=12, pady=(12, 8))

        # Filtro de Linha de Produto
        self.combo_filtro_linha_kits = ctk.CTkComboBox(
            col_esquerda,
            values=["Todas as Linhas"] + LINHAS_PRODUTO,
            state="readonly",
            height=32,
            font=ctk.CTkFont(size=11),
            command=lambda _: self._renderizar_lista_kits()
        )
        self.combo_filtro_linha_kits.set("Todas as Linhas")
        self.combo_filtro_linha_kits.pack(fill="x", padx=12, pady=(0, 6))

        # Campo de busca de kits
        self.entry_busca_kit = ctk.CTkEntry(
            col_esquerda,
            placeholder_text="🔎 Filtrar kits cadastrados...",
            height=34,
            font=ctk.CTkFont(size=12)
        )
        self.entry_busca_kit.pack(fill="x", padx=12, pady=(0, 8))
        self.entry_busca_kit.bind("<KeyRelease>", lambda e: self._renderizar_lista_kits())

        # Lista com scroll para os kits
        self.scroll_kits = ctk.CTkScrollableFrame(col_esquerda, corner_radius=6)
        self.scroll_kits.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # --- COLUNA DIREITA: DETALHES / FORMULÁRIO ---
        self.col_direita = ctk.CTkFrame(corpo, corner_radius=10)
        self.col_direita.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

    def _carregar_dados(self):
        """Carrega dados do storage e atualiza telas."""
        self.kits_cadastrados = self.storage.obter_catalogo_kits()
        self.todas_pecas = self.storage.listar_todas_pecas()
        self._renderizar_lista_kits()

        if self.modo_novo_kit or not self.kit_selecionado:
            self._renderizar_formulario_novo_kit()
        else:
            self._renderizar_painel_kit_selecionado()

    def _renderizar_lista_kits(self):
        """Renderiza a lista de botões/cards dos kits na coluna esquerda com filtro de linha e badges."""
        for w in self.scroll_kits.winfo_children():
            w.destroy()

        termo = self.entry_busca_kit.get().strip().lower()
        filtro_linha = self.combo_filtro_linha_kits.get() if hasattr(self, "combo_filtro_linha_kits") else "Todas as Linhas"

        kits_filtrados = []
        for k in self.kits_cadastrados:
            nome = k.get("nome", "")
            linha_k = k.get("linha", "MedicalFix") or "MedicalFix"
            if filtro_linha != "Todas as Linhas":
                if linha_k.lower() != filtro_linha.lower() and linha_k not in ("Todas as Linhas", "Todas", "Geral", ""):
                    continue
            if termo and termo not in nome.lower() and termo not in linha_k.lower():
                continue
            kits_filtrados.append(k)

        if not kits_filtrados:
            msg = "Nenhum kit encontrado." if self.kits_cadastrados else "Nenhum kit cadastrado.\nClique em '+ NOVO KIT' acima."
            ctk.CTkLabel(
                self.scroll_kits,
                text=msg,
                text_color="gray",
                font=ctk.CTkFont(size=11),
                justify="center"
            ).pack(pady=30)
            return

        for k in kits_filtrados:
            nome = k.get("nome", "")
            linha_k = k.get("linha", "MedicalFix") or "MedicalFix"
            pecas_vinculadas = self.storage.obter_pecas_do_kit(nome)
            qtd = len(pecas_vinculadas)

            is_sel = (not self.modo_novo_kit and self.kit_selecionado and self.kit_selecionado.get("nome") == nome)
            bg = ("#cce5ff", "#1f3b5c") if is_sel else ("#f0f0f0", "#1e2228")

            card = ctk.CTkFrame(self.scroll_kits, fg_color=bg, corner_radius=6, height=44)
            card.pack(fill="x", pady=3, padx=2)
            card.pack_propagate(False)

            def bind_clique(widget, item=k):
                widget.bind("<Button-1>", lambda e: self._selecionar_kit(item))
                for c in widget.winfo_children():
                    bind_clique(c, item)

            lbl_nome = ctk.CTkLabel(
                card,
                text=f"🏷️  {nome}",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            lbl_nome.pack(side="left", fill="x", expand=True, padx=8)

            badge_linha = ctk.CTkLabel(
                card,
                text=linha_k,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color=("#dfe7ef", "#2a3441") if not is_sel else "#144d75",
                text_color=("#1f6aa5", "#64b5f6") if not is_sel else "white",
                corner_radius=4,
                width=65,
                height=20
            )
            badge_linha.pack(side="right", padx=(0, 4))

            badge = ctk.CTkLabel(
                card,
                text=f"{qtd} itens",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#334d66" if not is_sel else "#144d75",
                text_color="white",
                corner_radius=4,
                width=50,
                height=20
            )
            badge.pack(side="right", padx=(0, 4))

            bind_clique(card, k)

    def _iniciar_modo_novo_kit(self):
        self.modo_novo_kit = True
        self.kit_selecionado = None
        self._renderizar_lista_kits()
        self._renderizar_formulario_novo_kit()

    def _selecionar_kit(self, kit: Dict[str, Any]):
        self.modo_novo_kit = False
        self.kit_selecionado = kit
        self._renderizar_lista_kits()
        self._renderizar_painel_kit_selecionado()

    # ==========================================
    # PAINEL DIREITO: CADASTRO DE NOVO KIT
    # ==========================================
    def _renderizar_formulario_novo_kit(self):
        for w in self.col_direita.winfo_children():
            w.destroy()

        container = ctk.CTkScrollableFrame(self.col_direita, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        lbl_tit = ctk.CTkLabel(
            container,
            text="➕ CADASTRAR NOVO KIT",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_tit.pack(anchor="w", pady=(0, 2))

        lbl_sub = ctk.CTkLabel(
            container,
            text="Preencha os dados do kit e selecione quais peças/montagens já devem fazer parte dele.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        lbl_sub.pack(anchor="w", pady=(0, 15))

        # Nome do Kit
        ctk.CTkLabel(container, text="Nome do Kit (obrigatório):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.entry_nome_kit = ctk.CTkEntry(
            container,
            placeholder_text="Ex: Kit Cirúrgico Implante, Kit Torquímetro...",
            font=ctk.CTkFont(size=13),
            height=38
        )
        self.entry_nome_kit.pack(fill="x", pady=(0, 12))

        # Linha de Produto
        ctk.CTkLabel(container, text="Linha de Produto:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.combo_linha_novo_kit = ctk.CTkComboBox(
            container,
            values=LINHAS_PRODUTO,
            state="readonly",
            height=36,
            font=ctk.CTkFont(size=12)
        )
        self.combo_linha_novo_kit.set("MedicalFix")
        self.combo_linha_novo_kit.pack(fill="x", pady=(0, 12))

        # Descrição do Kit
        ctk.CTkLabel(container, text="Descrição / Finalidade (opcional):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        self.entry_desc_kit = ctk.CTkEntry(
            container,
            placeholder_text="Ex: Conjunto cirúrgico com torquímetro e chaves para implante cônico...",
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.entry_desc_kit.pack(fill="x", pady=(0, 15))

        # Seleção de Peças Iniciais
        frame_pecas = ctk.CTkFrame(container, fg_color=("#ebebeb", "#20242b"), corner_radius=8)
        frame_pecas.pack(fill="both", expand=True, pady=(0, 15))

        lbl_pecas_tit = ctk.CTkLabel(
            frame_pecas,
            text="📦 Selecionar Peças ou Montagens para Este Kit (opcional):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_pecas_tit.pack(anchor="w", padx=12, pady=(10, 4))

        self.entry_busca_pecas_novo = ctk.CTkEntry(
            frame_pecas,
            placeholder_text="🔎 Filtrar peças por código ou nome...",
            height=32,
            font=ctk.CTkFont(size=11)
        )
        self.entry_busca_pecas_novo.pack(fill="x", padx=12, pady=(0, 8))
        self.entry_busca_pecas_novo.bind("<KeyRelease>", lambda e: self._filtrar_pecas_novo_kit())

        self.scroll_pecas_novo = ctk.CTkScrollableFrame(frame_pecas, height=180, fg_color="transparent")
        self.scroll_pecas_novo.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.vars_pecas_novo: Dict[str, ctk.BooleanVar] = {}
        self._filtrar_pecas_novo_kit()

        # Botão Salvar
        btn_salvar = ctk.CTkButton(
            container,
            text="💾 CADASTRAR KIT",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2fa572",
            hover_color="#227a54",
            height=42,
            command=self._salvar_novo_kit
        )
        btn_salvar.pack(fill="x", pady=(5, 10))

    def _filtrar_pecas_novo_kit(self):
        for w in self.scroll_pecas_novo.winfo_children():
            w.destroy()

        termo = self.entry_busca_pecas_novo.get().strip().lower()
        filtradas = [
            p for p in self.todas_pecas
            if not termo or (termo in p.codigo.lower() or termo in p.nome.lower())
        ]

        if not filtradas:
            ctk.CTkLabel(self.scroll_pecas_novo, text="Nenhuma peça encontrada.", text_color="gray").pack(pady=10)
            return

        for p in filtradas:
            var = self.vars_pecas_novo.setdefault(p.codigo, ctk.BooleanVar(value=False))
            linha = ctk.CTkFrame(self.scroll_pecas_novo, fg_color="transparent")
            linha.pack(fill="x", pady=2)

            linha_p = getattr(p, "linha_produto", "MedicalFix") or "MedicalFix"
            chk = ctk.CTkCheckBox(
                linha,
                text=f"{p.codigo} — {p.nome} ({p.tipo})  [{linha_p}]",
                variable=var,
                font=ctk.CTkFont(size=11)
            )
            chk.pack(side="left", padx=5)

    def _salvar_novo_kit(self):
        nome = self.entry_nome_kit.get().strip()
        descricao = self.entry_desc_kit.get().strip()
        linha = self.combo_linha_novo_kit.get().strip() if hasattr(self, "combo_linha_novo_kit") else "MedicalFix"

        if not nome:
            messagebox.showwarning("Aviso", "Por favor, digite o nome do kit.", parent=self)
            self.entry_nome_kit.focus()
            return

        sucesso, msg = self.storage.cadastrar_kit(nome, descricao, linha=linha)
        if not sucesso:
            messagebox.showerror("Erro ao Cadastrar Kit", msg, parent=self)
            return

        # Vincula peças que foram marcadas
        pecas_selecionadas = [cod for cod, var in self.vars_pecas_novo.items() if var.get()]
        for cod in pecas_selecionadas:
            self.storage.vincular_peca_a_kit(cod, nome)

        msg_sucesso = f"✓ Kit '{nome}' cadastrado com sucesso!"
        if pecas_selecionadas:
            msg_sucesso += f"\n\n{len(pecas_selecionadas)} peça(s)/montagem(ns) vinculada(s) a este kit."

        messagebox.showinfo("Kit Cadastrado", msg_sucesso, parent=self)

        if self.on_change:
            self.on_change()

        # Seleciona o novo kit no catálogo
        self.kits_cadastrados = self.storage.obter_catalogo_kits()
        self.todas_pecas = self.storage.listar_todas_pecas()
        kit_criado = next((k for k in self.kits_cadastrados if k.get("nome", "").lower() == nome.lower()), None)
        if kit_criado:
            self._selecionar_kit(kit_criado)
        else:
            self._carregar_dados()

    # ==========================================
    # PAINEL DIREITO: DETALHES DO KIT SELECIONADO
    # ==========================================
    def _renderizar_painel_kit_selecionado(self):
        for w in self.col_direita.winfo_children():
            w.destroy()

        if not self.kit_selecionado:
            return

        nome_kit = self.kit_selecionado.get("nome", "")
        desc_kit = self.kit_selecionado.get("descricao", "")
        criado_em = self.kit_selecionado.get("criado_em", "")

        container = ctk.CTkFrame(self.col_direita, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Cabeçalho do Kit
        head_kit = ctk.CTkFrame(container, fg_color="transparent")
        head_kit.pack(fill="x", pady=(0, 6))

        lbl_tit = ctk.CTkLabel(
            head_kit,
            text=f"🏷️  {nome_kit}",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        lbl_tit.pack(side="left")

        # Botões de Ação do Kit (Renomear / Excluir)
        btn_excluir = ctk.CTkButton(
            head_kit,
            text="🗑️ Excluir",
            width=80,
            height=30,
            fg_color="#b83232",
            hover_color="#8c2323",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._confirmar_excluir_kit
        )
        btn_excluir.pack(side="right", padx=(5, 0))

        btn_renomear = ctk.CTkButton(
            head_kit,
            text="✏️ Renomear",
            width=90,
            height=30,
            fg_color="#444444",
            hover_color="#333333",
            font=ctk.CTkFont(size=11),
            command=self._abrir_dialogo_renomear
        )
        btn_renomear.pack(side="right")

        # Linha de Produto e Ação de Troca
        linha_kit = self.kit_selecionado.get("linha", "MedicalFix") or "MedicalFix"
        linha_meta = ctk.CTkFrame(container, fg_color="transparent")
        linha_meta.pack(fill="x", pady=(0, 8))

        badge_linha_detalhe = ctk.CTkLabel(
            linha_meta,
            text=f"Linha de Produto: {linha_kit}",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#dfe7ef", "#1f3b5c"),
            text_color=("#1f6aa5", "#64b5f6"),
            corner_radius=4,
            height=24,
            padx=10
        )
        badge_linha_detalhe.pack(side="left")

        def _alterar_linha_kit():
            popup_linha = ctk.CTkToplevel(self)
            popup_linha.title("Alterar Linha")
            popup_linha.geometry("320x170")
            popup_linha.minsize(300, 160)
            popup_linha.grab_set()
            popup_linha.transient(self)

            ctk.CTkLabel(
                popup_linha,
                text=f"Linha de produto para '{nome_kit}':",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(padx=20, pady=(15, 8))

            combo_mudar = ctk.CTkComboBox(popup_linha, values=LINHAS_PRODUTO, state="readonly", height=34)
            combo_mudar.set(linha_kit if linha_kit in LINHAS_PRODUTO else "MedicalFix")
            combo_mudar.pack(fill="x", padx=20, pady=(0, 15))

            def _salvar_mudar():
                nova = combo_mudar.get()
                ok, msg = self.storage.editar_kit(nome_kit, nome_kit, linha_nova=nova)
                popup_linha.destroy()
                if ok:
                    if self.on_change:
                        self.on_change()
                    self.kits_cadastrados = self.storage.obter_catalogo_kits()
                    self.kit_selecionado = next((k for k in self.kits_cadastrados if k.get("nome", "").lower() == nome_kit.lower()), None)
                    self._renderizar_lista_kits()
                    self._renderizar_painel_kit_selecionado()

            ctk.CTkButton(popup_linha, text="CONFIRMAR", font=ctk.CTkFont(weight="bold"), height=32, command=_salvar_mudar).pack(fill="x", padx=20)

        btn_trocar_linha = ctk.CTkButton(
            linha_meta,
            text="✏️ Alterar Linha...",
            height=24,
            width=110,
            font=ctk.CTkFont(size=11),
            fg_color="#334d66",
            hover_color="#24384a",
            command=_alterar_linha_kit
        )
        btn_trocar_linha.pack(side="left", padx=(8, 0))

        if desc_kit:
            lbl_desc = ctk.CTkLabel(
                container,
                text=desc_kit,
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
                justify="left"
            )
            lbl_desc.pack(fill="x", pady=(0, 5))

        if criado_em:
            lbl_data = ctk.CTkLabel(
                container,
                text=f"Cadastrado em: {criado_em}",
                font=ctk.CTkFont(size=10),
                text_color="gray",
                anchor="w"
            )
            lbl_data.pack(fill="x", pady=(0, 10))

        # Divisor
        ctk.CTkFrame(container, height=1, fg_color=("#d0d0d0", "#333842")).pack(fill="x", pady=(0, 10))

        # Seção Peças Vinculadas
        pecas_do_kit = self.storage.obter_pecas_do_kit(nome_kit)
        lbl_sec = ctk.CTkLabel(
            container,
            text=f"📦 Peças e Montagens Neste Kit ({len(pecas_do_kit)}):",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_sec.pack(anchor="w", pady=(0, 6))

        scroll_vinculadas = ctk.CTkScrollableFrame(container, height=180, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        scroll_vinculadas.pack(fill="both", expand=True, pady=(0, 12))

        if not pecas_do_kit:
            ctk.CTkLabel(
                scroll_vinculadas,
                text="Nenhuma peça vinculada a este kit ainda.\nAdicione peças abaixo.",
                text_color="gray",
                font=ctk.CTkFont(size=11)
            ).pack(pady=20)
        else:
            for p in pecas_do_kit:
                linha_p = ctk.CTkFrame(scroll_vinculadas, fg_color=("white", "#23272e"), corner_radius=6, height=42)
                linha_p.pack(fill="x", pady=2, padx=4)
                linha_p.pack_propagate(False)

                img_thumb = self.thumbnail.obter_ctk_image(p, size=(40, 28))
                lbl_img = ctk.CTkLabel(linha_p, image=img_thumb, text="", width=45)
                lbl_img.pack(side="left", padx=4)

                lbl_info = ctk.CTkLabel(
                    linha_p,
                    text=f"{p.codigo} — {p.nome} ({p.tipo}) [Rev {p.revisao_atual}]",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    anchor="w"
                )
                lbl_info.pack(side="left", fill="x", expand=True, padx=6)

                btn_desvincular = ctk.CTkButton(
                    linha_p,
                    text="✕ Desvincular",
                    width=90,
                    height=26,
                    fg_color="#8c2323",
                    hover_color="#6e1b1b",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda cod=p.codigo: self._desvincular_peca(cod)
                )
                btn_desvincular.pack(side="right", padx=6)

        # Seção Adicionar Peças ao Kit
        frame_adicionar = ctk.CTkFrame(container, corner_radius=8, fg_color=("#ebebeb", "#20242b"))
        frame_adicionar.pack(fill="x", pady=(0, 5))

        lbl_add_tit = ctk.CTkLabel(
            frame_adicionar,
            text="➕ Adicionar Peça a Este Kit:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_add_tit.pack(anchor="w", padx=12, pady=(8, 4))

        linha_add = ctk.CTkFrame(frame_adicionar, fg_color="transparent")
        linha_add.pack(fill="x", padx=12, pady=(0, 10))

        # Lista de peças não inclusas
        codigos_ja_no_kit = {p.codigo.upper() for p in pecas_do_kit}
        pecas_disponiveis = [p for p in self.todas_pecas if p.codigo.upper() not in codigos_ja_no_kit]

        if pecas_disponiveis:
            # Prioriza peças pertencentes à mesma linha deste kit
            pecas_disponiveis.sort(key=lambda p: (
                0 if getattr(p, "linha_produto", "").lower() == linha_kit.lower() else 1,
                p.codigo
            ))
            opcoes = [f"{p.codigo} — {p.nome} ({p.tipo})  [{getattr(p, 'linha_produto', 'MedicalFix')}]" for p in pecas_disponiveis]
            self.combo_add_peca = ctk.CTkComboBox(
                linha_add,
                values=opcoes,
                state="readonly",
                height=34,
                font=ctk.CTkFont(size=11)
            )
            self.combo_add_peca.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.combo_add_peca.set(opcoes[0])

            btn_add = ctk.CTkButton(
                linha_add,
                text="Vincular ao Kit",
                font=ctk.CTkFont(size=11, weight="bold"),
                width=120,
                height=34,
                command=self._adicionar_peca_selecionada
            )
            btn_add.pack(side="right")
        else:
            ctk.CTkLabel(
                linha_add,
                text="Todas as peças já estão vinculadas a este kit.",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            ).pack(side="left")

    def _adicionar_peca_selecionada(self):
        if not hasattr(self, "combo_add_peca") or not self.kit_selecionado:
            return
        valor = self.combo_add_peca.get()
        codigo = valor.split("—")[0].strip()
        nome_kit = self.kit_selecionado.get("nome", "")

        sucesso = self.storage.vincular_peca_a_kit(codigo, nome_kit)
        if sucesso:
            if self.on_change:
                self.on_change()
            self._carregar_dados()

    def _desvincular_peca(self, codigo_peca: str):
        if not self.kit_selecionado:
            return
        nome_kit = self.kit_selecionado.get("nome", "")
        sucesso = self.storage.desvincular_peca_de_kit(codigo_peca, nome_kit)
        if sucesso:
            if self.on_change:
                self.on_change()
            self._carregar_dados()

    def _abrir_dialogo_renomear(self):
        if not self.kit_selecionado:
            return
        nome_atual = self.kit_selecionado.get("nome", "")

        dialog = ctk.CTkInputDialog(
            title="Renomear Kit",
            text=f"Digite o novo nome para o kit '{nome_atual}':"
        )
        novo_nome = dialog.get_input()
        if novo_nome and novo_nome.strip():
            sucesso, msg = self.storage.renomear_kit(nome_atual, novo_nome.strip())
            if sucesso:
                messagebox.showinfo("Kit Renomeado", msg, parent=self)
                if self.on_change:
                    self.on_change()
                self.kits_cadastrados = self.storage.obter_catalogo_kits()
                kit_atualizado = next((k for k in self.kits_cadastrados if k.get("nome", "").lower() == novo_nome.strip().lower()), None)
                if kit_atualizado:
                    self._selecionar_kit(kit_atualizado)
                else:
                    self._carregar_dados()
            else:
                messagebox.showerror("Erro ao Renomear", msg, parent=self)

    def _confirmar_excluir_kit(self):
        if not self.kit_selecionado:
            return
        nome_kit = self.kit_selecionado.get("nome", "")
        pecas = self.storage.obter_pecas_do_kit(nome_kit)

        msg = f"Tem certeza que deseja excluir o kit '{nome_kit}'?\n\n"
        if pecas:
            msg += f"Este kit está associado a {len(pecas)} peça(s)/montagem(ns).\n"
            msg += "Elas continuarão cadastradas, mas o vínculo com este kit será removido."
        else:
            msg += "Nenhuma peça está vinculada a este kit no momento."

        confirma = messagebox.askyesno("Confirmar Exclusão de Kit", msg, parent=self)
        if confirma:
            sucesso, msg_res = self.storage.excluir_kit(nome_kit, desvincular_pecas=True)
            if sucesso:
                messagebox.showinfo("Kit Excluído", msg_res, parent=self)
                if self.on_change:
                    self.on_change()
                self._iniciar_modo_novo_kit()
                self._carregar_dados()
            else:
                messagebox.showerror("Erro ao Excluir", msg_res, parent=self)
