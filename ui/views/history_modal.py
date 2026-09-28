"""
Modal de Visualização do Histórico de Revisões do Controle CAD.
Exibe a tabela cronológica de revisões, autores, datas e motivos,
além de acesso às pastas arquivadas no HISTORICO.
"""

import os
import customtkinter as ctk
from core.models import PecaInfo


class HistoryModal(ctk.CTkToplevel):
    def __init__(self, parent, peca: PecaInfo):
        super().__init__(parent)
        self.parent = parent
        self.peca = peca

        self.title(f"Histórico — {self.peca.codigo} - {self.peca.nome}")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        largura = min(sw - 40, 720)
        altura = min(sh - 80, 560)
        self.geometry(f"{largura}x{altura}")
        self.minsize(580, 420)
        self.resizable(True, True)
        self.transient(parent)

        self._construir_ui()

    def _construir_ui(self):
        # Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(16, 8))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text=f"HISTÓRICO DE REVISÕES: {self.peca.codigo} - {self.peca.nome}",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text=f"Tipo: {self.peca.tipo} | Revisão Atual: {self.peca.revisao_atual} | Criado por: {self.peca.criado_por} em {self.peca.criado_em}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Seção de Acesso ao Histórico Físico / Rodapé (Dockado ao fundo para nunca sumir)
        pasta_historico = os.path.join(self.peca.pasta_path, "HISTORICO")
        revs_arquivadas = []
        if os.path.exists(pasta_historico):
            revs_arquivadas = [
                d for d in os.listdir(pasta_historico)
                if os.path.isdir(os.path.join(pasta_historico, d)) and d.upper().startswith("REV_")
            ]
            revs_arquivadas.sort()

        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=20, pady=(8, 15), side="bottom")

        if revs_arquivadas:
            lbl_arquivos = ctk.CTkLabel(
                footer_frame,
                text=f"Arquivos históricos disponíveis: {', '.join(revs_arquivadas)}",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            lbl_arquivos.pack(side="left")

            btn_abrir_hist = ctk.CTkButton(
                footer_frame,
                text="📁 ABRIR PASTA HISTÓRICO",
                width=180,
                height=34,
                command=lambda: os.startfile(pasta_historico)
            )
            btn_abrir_hist.pack(side="right", padx=(10, 0))

        btn_fechar = ctk.CTkButton(
            footer_frame,
            text="FECHAR",
            width=100,
            height=34,
            fg_color="#555555",
            hover_color="#444444",
            command=self.destroy
        )
        btn_fechar.pack(side="right")

        # Tabela de Histórico (Scrollable Frame)
        table_container = ctk.CTkScrollableFrame(self, corner_radius=10)
        table_container.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Cabeçalho da Tabela
        cols_header = ctk.CTkFrame(table_container, fg_color=("#e1e1e1", "#2b2b2b"), height=35)
        cols_header.pack(fill="x", pady=(0, 6), padx=4)

        ctk.CTkLabel(cols_header, text="REV", width=50, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(cols_header, text="DATA", width=130, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(cols_header, text="USUÁRIO", width=110, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(cols_header, text="MOTIVO DA ALTERAÇÃO", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10, fill="x", expand=True)

        # Linhas de Histórico
        if not self.peca.historico:
            ctk.CTkLabel(
                table_container,
                text="Nenhum histórico registrado para esta peça.",
                text_color="gray"
            ).pack(pady=30)
        else:
            for idx, h in enumerate(self.peca.historico):
                bg_color = ("#f7f7f7", "#222222") if idx % 2 == 0 else ("#ededed", "#1e1e1e")
                row = ctk.CTkFrame(table_container, fg_color=bg_color, height=36, corner_radius=6)
                row.pack(fill="x", pady=2, padx=4)

                # Badge de Revisão
                is_current = (h.revisao == self.peca.revisao_atual)
                rev_color = "#2fa572" if is_current else "#1f6aa5"
                rev_badge = ctk.CTkLabel(
                    row,
                    text=h.revisao,
                    width=40,
                    fg_color=rev_color,
                    text_color="white",
                    corner_radius=4,
                    font=ctk.CTkFont(weight="bold")
                )
                rev_badge.pack(side="left", padx=8, pady=4)

                ctk.CTkLabel(row, text=h.data, width=130, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=h.usuario, width=110, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=h.motivo, anchor="w").pack(side="left", padx=10, fill="x", expand=True)
