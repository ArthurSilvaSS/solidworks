"""
Modal para Gerenciamento de Kits de Peças e Montagens no Controle CAD.
Permite vincular uma peça/montagem a um ou múltiplos kits e criar novos kits dinamicamente.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import List, Callable, Optional, Set
from core.models import PecaInfo
from services.storage_service import StorageService
from core.logger import registrar_log


class ManageKitsModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        peca: PecaInfo,
        storage_service: StorageService,
        on_success_callback: Callable[[PecaInfo], None]
    ):
        super().__init__(parent)
        self.parent = parent
        self.peca = peca
        self.storage = storage_service
        self.on_success = on_success_callback

        # Cópia dos kits para edição
        self.kits_atuais: Set[str] = set(self.peca.kits)

        self.title(f"Kits — {self.peca.codigo}")
        screen_h = self.winfo_screenheight()
        altura = min(screen_h - 100, 620)
        self.geometry(f"540x{altura}")
        self.minsize(480, 420)
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._construir_ui()

    def _construir_ui(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", side="top", padx=25, pady=(15, 6))

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text=f"GERENCIAR KITS — {self.peca.codigo}",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        lbl_titulo.pack(anchor="w")

        linha_peca = getattr(self.peca, "linha_produto", "MedicalFix") or "MedicalFix"
        lbl_sub = ctk.CTkLabel(
            header_frame,
            text=f"{self.peca.nome}  •  {self.peca.tipo}  •  Linha: {linha_peca}  •  Rev {self.peca.revisao_atual}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#1f6aa5", "#64b5f6")
        )
        lbl_sub.pack(anchor="w", pady=(2, 2))

        lbl_desc = ctk.CTkLabel(
            header_frame,
            text="Defina em quais kits este item faz parte (ex: Kit Cirúrgico, Kit Implante, etc.).",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        lbl_desc.pack(anchor="w")

        # 2. Botões de Rodapé Fixos (Garante que nunca fiquem invisíveis)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", padx=25, pady=(10, 15))

        btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=38,
            command=self.destroy
        )
        btn_cancelar.pack(side="left")

        btn_salvar = ctk.CTkButton(
            btn_frame,
            text="SALVAR KITS ➔",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            height=38,
            command=self._salvar_alteracoes
        )
        btn_salvar.pack(side="right")

        # 3. Conteúdo Central Rolável
        conteudo_scroll = ctk.CTkScrollableFrame(self, corner_radius=10)
        conteudo_scroll.pack(fill="both", expand=True, padx=25, pady=(0, 5))

        # Painel de Kits Atualmente Vinculados
        frame_atuais = ctk.CTkFrame(conteudo_scroll, corner_radius=8, fg_color=("#f0f0f0", "#1e2228"))
        frame_atuais.pack(fill="x", pady=(5, 10))

        lbl_tit_atuais = ctk.CTkLabel(
            frame_atuais,
            text="🏷️ Kits Vinculados a Este Item:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_tit_atuais.pack(anchor="w", padx=15, pady=(10, 4))

        self.container_chips = ctk.CTkFrame(frame_atuais, fg_color="transparent")
        self.container_chips.pack(fill="x", padx=12, pady=(0, 10))
        self._renderizar_chips_atuais()

        # Adicionar a Novo Kit
        frame_novo = ctk.CTkFrame(conteudo_scroll, corner_radius=8, fg_color=("#ebebeb", "#23272e"))
        frame_novo.pack(fill="x", pady=(0, 10))

        lbl_tit_novo = ctk.CTkLabel(
            frame_novo,
            text="+ Vincular a um Novo Kit:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_tit_novo.pack(anchor="w", padx=15, pady=(8, 4))

        linha_novo = ctk.CTkFrame(frame_novo, fg_color="transparent")
        linha_novo.pack(fill="x", padx=12, pady=(0, 10))

        self.entry_novo_kit = ctk.CTkEntry(
            linha_novo,
            placeholder_text="Digite o nome do kit (ex: Kit Cirúrgico Pro)...",
            font=ctk.CTkFont(size=12),
            height=34
        )
        self.entry_novo_kit.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_novo_kit.bind("<Return>", lambda e: self._adicionar_novo_kit())

        btn_add = ctk.CTkButton(
            linha_novo,
            text="+ Vincular",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=95,
            height=34,
            fg_color="#2fa572",
            hover_color="#227a53",
            command=self._adicionar_novo_kit
        )
        btn_add.pack(side="left")

        # Lista de Kits Existentes na Empresa (para seleção rápida)
        frame_existentes = ctk.CTkFrame(conteudo_scroll, corner_radius=8)
        frame_existentes.pack(fill="both", expand=True, pady=(0, 5))

        lbl_tit_existentes = ctk.CTkLabel(
            frame_existentes,
            text="📋 Kits Cadastrados na Empresa (marque para vincular):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_tit_existentes.pack(anchor="w", padx=15, pady=(10, 4))

        self.scroll_existentes = ctk.CTkScrollableFrame(frame_existentes, height=180, corner_radius=6)
        self.scroll_existentes.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._carregar_kits_existentes()

    def _renderizar_chips_atuais(self):
        for w in self.container_chips.winfo_children():
            w.destroy()

        if not self.kits_atuais:
            ctk.CTkLabel(
                self.container_chips,
                text="Nenhum kit vinculado a este item atualmente.",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            ).pack(anchor="w", padx=5, pady=4)
            return

        # Frame com fluxo de tags
        tags_row = ctk.CTkFrame(self.container_chips, fg_color="transparent")
        tags_row.pack(fill="x", pady=2)

        for kit_nome in sorted(self.kits_atuais, key=lambda s: s.lower()):
            chip = ctk.CTkFrame(
                tags_row,
                corner_radius=14,
                fg_color=("#d0e3f7", "#173552"),
                height=28
            )
            chip.pack(side="left", padx=3, pady=3)

            lbl_txt = ctk.CTkLabel(
                chip,
                text=f"🏷️ {kit_nome}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#124d85", "#79b8f5")
            )
            lbl_txt.pack(side="left", padx=(8, 4), pady=2)

            btn_rem = ctk.CTkButton(
                chip,
                text="✕",
                width=18,
                height=18,
                corner_radius=9,
                fg_color="transparent",
                hover_color=("#b3cde8", "#244d73"),
                text_color=("#124d85", "#79b8f5"),
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda k=kit_nome: self._remover_kit(k)
            )
            btn_rem.pack(side="left", padx=(0, 6), pady=2)

    def _carregar_kits_existentes(self):
        for w in self.scroll_existentes.winfo_children():
            w.destroy()

        linha_p = getattr(self.peca, "linha_produto", "MedicalFix") or "MedicalFix"
        catalogo = self.storage.obter_catalogo_kits()
        mapa_linhas = {k.get("nome", "").lower(): k.get("linha", "MedicalFix") for k in catalogo}

        todos_kits = self.storage.obter_todos_kits()
        # Garante que os kits atuais também apareçam na lista de disponíveis
        for k in self.kits_atuais:
            if k not in todos_kits:
                todos_kits.append(k)

        # Ordena priorizando kits da mesma linha de produto da peça
        todos_kits.sort(key=lambda s: (
            0 if mapa_linhas.get(s.lower(), "").lower() == linha_p.lower() else 1,
            s.lower()
        ))

        if not todos_kits:
            ctk.CTkLabel(
                self.scroll_existentes,
                text="Nenhum kit cadastrado ainda. Use o campo acima para criar o primeiro kit.",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            ).pack(pady=20)
            return

        self.checkbox_vars = {}
        for kit_nome in todos_kits:
            var = ctk.BooleanVar(value=(kit_nome in self.kits_atuais))
            self.checkbox_vars[kit_nome] = var

            linha_k = mapa_linhas.get(kit_nome.lower(), "MedicalFix")

            linha = ctk.CTkFrame(self.scroll_existentes, fg_color="transparent")
            linha.pack(fill="x", pady=2)

            chk = ctk.CTkCheckBox(
                linha,
                text=f"🏷️  {kit_nome}",
                variable=var,
                font=ctk.CTkFont(size=12),
                command=lambda k=kit_nome, v=var: self._ao_alternar_checkbox(k, v)
            )
            chk.pack(side="left", padx=5)

            ctk.CTkLabel(
                linha,
                text=linha_k,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color=("#dfe7ef", "#2a3441"),
                text_color=("#1f6aa5", "#64b5f6"),
                corner_radius=4,
                width=65,
                height=18
            ).pack(side="right", padx=6)

    def _ao_alternar_checkbox(self, kit_nome: str, var: ctk.BooleanVar):
        if var.get():
            self.kits_atuais.add(kit_nome)
        else:
            self.kits_atuais.discard(kit_nome)
        self._renderizar_chips_atuais()

    def _adicionar_novo_kit(self):
        nome = self.entry_novo_kit.get().strip()
        if not nome:
            messagebox.showwarning("Aviso", "Digite o nome do kit a ser vinculado.", parent=self)
            self.entry_novo_kit.focus()
            return

        linha_p = getattr(self.peca, "linha_produto", "MedicalFix") or "MedicalFix"

        # Verifica se já está vinculado
        for k in self.kits_atuais:
            if k.lower() == nome.lower():
                messagebox.showinfo("Aviso", f"O kit '{k}' já está vinculado a esta peça.", parent=self)
                self.entry_novo_kit.delete(0, "end")
                return

        # Cadastra no storage garantindo linha de produto da peça
        self.storage.cadastrar_kit(nome, linha=linha_p)

        self.kits_atuais.add(nome)
        self.entry_novo_kit.delete(0, "end")
        self._renderizar_chips_atuais()
        self._carregar_kits_existentes()

    def _remover_kit(self, kit_nome: str):
        self.kits_atuais.discard(kit_nome)
        self._renderizar_chips_atuais()
        if hasattr(self, "checkbox_vars") and kit_nome in self.checkbox_vars:
            self.checkbox_vars[kit_nome].set(False)

    def _salvar_alteracoes(self):
        lista_kits = sorted(self.kits_atuais, key=lambda s: s.lower())
        self.peca.kits = lista_kits

        # Salva no controle.json
        sucesso = self.storage.salvar_controle_json(self.peca)
        if not sucesso:
            messagebox.showerror("Erro", "Não foi possível salvar as alterações no controle.json da peça.", parent=self)
            return

        registrar_log(
            "KITS ATUALIZADOS",
            {
                "Código": self.peca.codigo,
                "Nome": self.peca.nome,
                "Tipo": self.peca.tipo,
                "Kits": ", ".join(lista_kits) or "Nenhum"
            }
        )

        messagebox.showinfo(
            "Kits Salvos",
            f"✓ Vínculo de kits atualizado com sucesso para '{self.peca.codigo} - {self.peca.nome}'!\n\n"
            f"Kits: {', '.join(lista_kits) if lista_kits else 'Nenhum'}",
            parent=self
        )

        self.on_success(self.peca)
        self.destroy()
