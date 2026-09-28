"""
Modal de Confirmação para Exclusão Definitiva de Desenho e Pastas.
Permite ao projetista excluir um desenho existente, removendo com segurança
todas as pastas vinculadas (CAD, DESENHO, PDF, HISTORICO) e seus arquivos.
"""

import os
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional
from core.models import PecaInfo
from services.storage_service import StorageService


class ConfirmDeleteModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        peca: PecaInfo,
        storage_service: StorageService,
        sw_client,
        on_success_callback: Callable[[PecaInfo], None]
    ):
        super().__init__(parent)
        self.parent = parent
        self.peca = peca
        self.storage = storage_service
        self.sw_client = sw_client
        self.on_success = on_success_callback

        self.title("Excluir Desenho — Controle CAD")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        altura = min(sh - 80, 590)
        largura = min(sw - 40, 560)
        self.geometry(f"{largura}x{altura}")
        self.minsize(480, 460)
        self.resizable(True, True)
        self.grab_set()  # Modal bloqueante
        self.transient(parent)

        self._construir_ui()

    def _construir_ui(self):
        # 1. CABEÇALHO COM ALERTA
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(16, 8))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="🗑️ EXCLUIR DESENHO E TODAS AS PASTAS",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#ff5c5c"
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="Esta ação removerá permanentemente o projeto e todas as suas pastas do disco.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc_lbl.pack(anchor="w", pady=(2, 0))

        # 2. CARTÃO DE INFORMAÇÕES DA PEÇA
        info_card = ctk.CTkFrame(self, fg_color=("#ebebeb", "#20252d"), corner_radius=10)
        info_card.pack(fill="x", padx=25, pady=(5, 12))

        # Linha superior: Código, Tipo e Revisão
        top_row = ctk.CTkFrame(info_card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(12, 4))

        lbl_codigo = ctk.CTkLabel(
            top_row,
            text=self.peca.codigo,
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=("#1f6aa5", "#4ea8de")
        )
        lbl_codigo.pack(side="left")

        rev_badge = ctk.CTkLabel(
            top_row,
            text=f"Rev {self.peca.revisao_atual}",
            fg_color="#2fa572",
            text_color="white",
            corner_radius=4,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=50,
            height=22
        )
        rev_badge.pack(side="left", padx=10)

        tipo_badge = ctk.CTkLabel(
            top_row,
            text=self.peca.tipo.upper(),
            fg_color=("#dddddd", "#2d3440"),
            text_color="gray",
            corner_radius=4,
            font=ctk.CTkFont(size=10, weight="bold"),
            width=70,
            height=22
        )
        tipo_badge.pack(side="left")

        # Nome da Peça
        lbl_nome = ctk.CTkLabel(
            info_card,
            text=self.peca.nome,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w"
        )
        lbl_nome.pack(fill="x", padx=16, pady=(0, 2))

        # Caminho da Pasta
        caminho_exibir = self.peca.pasta_path or self.storage.obter_pasta_peca(self.peca.codigo, self.peca.nome)
        lbl_caminho = ctk.CTkLabel(
            info_card,
            text=f"Diretório: {caminho_exibir}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="gray",
            anchor="w",
            wraplength=500
        )
        lbl_caminho.pack(fill="x", padx=16, pady=(0, 12))

        # 3. DETALHAMENTO DAS PASTAS A SEREM REMOVIDAS
        pastas_box = ctk.CTkFrame(self, fg_color=("#f3f4f6", "#1a1d23"), corner_radius=8)
        pastas_box.pack(fill="x", padx=25, pady=(0, 12))

        lbl_pastas_title = ctk.CTkLabel(
            pastas_box,
            text="Pastas e arquivos que serão totalmente excluídos:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        lbl_pastas_title.pack(fill="x", padx=14, pady=(10, 6))

        itens_excluidos = [
            ("📁 CAD/", "Modelos 3D (.SLDPRT ou .SLDASM)"),
            ("📁 DESENHO/", "Pranchas e desenhos técnicos 2D (.SLDDRW)"),
            ("📁 PDF/", "Cópias exportadas em formato .pdf"),
            ("📁 HISTORICO/", "Todas as revisões e versões arquivadas (REV_A, etc.)"),
            ("📄 Arquivos extras", "Metadados de controle.json e miniaturas 3D"),
        ]

        for item, desc in itens_excluidos:
            row = ctk.CTkFrame(pastas_box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=1)

            lbl_item = ctk.CTkLabel(
                row,
                text=item,
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=("#b83232", "#ff7878"),
                width=140,
                anchor="w"
            )
            lbl_item.pack(side="left")

            lbl_desc = ctk.CTkLabel(
                row,
                text=f"— {desc}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            lbl_desc.pack(side="left")

        # Espaçador
        ctk.CTkLabel(pastas_box, text="", height=4).pack()

        # 4. CARD DE AVISO DE RISCO
        alerta_frame = ctk.CTkFrame(self, fg_color=("#fdeeed", "#341f22"), corner_radius=8, border_width=1, border_color="#e74c3c")
        alerta_frame.pack(fill="x", padx=25, pady=(0, 15))

        lbl_alerta = ctk.CTkLabel(
            alerta_frame,
            text="⚠️ ATENÇÃO: Esta ação é definitiva e irreversível!\nTodos os arquivos serão deletados e não poderão ser recuperados.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#e74c3c",
            justify="center"
        )
        lbl_alerta.pack(padx=12, pady=10)

        # 5. CHECKBOX DE CONFIRMAÇÃO DE SEGURANÇA
        self.check_var = ctk.BooleanVar(value=False)
        self.check_confirmar = ctk.CTkCheckBox(
            self,
            text="Estou ciente de que todos os arquivos e pastas serão excluídos permanentemente",
            variable=self.check_var,
            font=ctk.CTkFont(size=11),
            command=self._ao_alterar_confirmacao
        )
        self.check_confirmar.pack(padx=25, pady=(0, 15), anchor="w")

        # 6. BOTÕES DE AÇÃO
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(0, 15), side="bottom")

        self.btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            font=ctk.CTkFont(size=13),
            fg_color="#444444",
            hover_color="#333333",
            height=40,
            width=120,
            command=self.destroy
        )
        self.btn_cancelar.pack(side="left")

        self.btn_excluir = ctk.CTkButton(
            btn_frame,
            text="🗑️ EXCLUIR DEFINITIVAMENTE",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#c9302c",
            hover_color="#9e2420",
            state="disabled",
            height=40,
            command=self._executar_exclusao
        )
        self.btn_excluir.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _ao_alterar_confirmacao(self):
        """Habilita o botão de exclusão apenas após a ciência do usuário."""
        if self.check_var.get():
            self.btn_excluir.configure(state="normal")
        else:
            self.btn_excluir.configure(state="disabled")

    def _executar_exclusao(self):
        """Executa a exclusão de todas as pastas do projeto."""
        if not self.check_var.get():
            messagebox.showwarning("Confirmação Necessária", "Por favor, marque a caixa confirmando a exclusão.", parent=self)
            return

        # Desabilita botões durante o processo
        self.btn_excluir.configure(state="disabled", text="Excluindo pastas...")
        self.btn_cancelar.configure(state="disabled")
        self.update_idletasks()

        sucesso, msg = self.storage.excluir_peca(self.peca, sw_client=self.sw_client)

        if sucesso:
            if self.on_success:
                self.on_success(self.peca)
            self.destroy()
            messagebox.showinfo("Desenho Excluído", msg, parent=self.parent)
        else:
            self.btn_excluir.configure(state="normal", text="🗑️ EXCLUIR DEFINITIVAMENTE")
            self.btn_cancelar.configure(state="normal")
            messagebox.showerror("Erro ao Excluir", msg, parent=self)
