"""
Modal/Janela de Validação Geral de Projetos.
Executa a auditoria da pasta raiz procurando pastas e arquivos fora do padrão,
inconsistências e estruturas incompletas, com relatório e opções de correção segura.
"""

import os
import customtkinter as ctk
from tkinter import messagebox
from typing import List
from core.models import ProblemaAuditoria
from services.audit_service import AuditService


class ValidationView(ctk.CTkToplevel):
    def __init__(self, parent, audit_service: AuditService):
        super().__init__(parent)
        self.parent = parent
        self.audit_service = audit_service

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        largura = min(sw - 40, 800)
        altura = min(sh - 80, 620)
        self.geometry(f"{largura}x{altura}")
        self.minsize(600, 440)
        self.resizable(True, True)
        self.transient(parent)

        self._construir_ui()
        self.executar_auditoria()

    def _construir_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(16, 8))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="RELATÓRIO DE AUDITORIA & CONFORMIDADE",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_lbl.pack(anchor="w")

        self.lbl_status = ctk.CTkLabel(
            header_frame,
            text="Verificando integridade das pastas e arquivos de engenharia...",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.lbl_status.pack(anchor="w")

        # Rodapé (Dockado ao fundo para sempre permanecer visível)
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=25, pady=(10, 16), side="bottom")

        self.btn_reexaminar = ctk.CTkButton(
            footer_frame,
            text="🔄 REEXAMINAR PROJETOS",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            height=38,
            command=self.executar_auditoria
        )
        self.btn_reexaminar.pack(side="left")

        self.btn_fechar = ctk.CTkButton(
            footer_frame,
            text="FECHAR",
            width=100,
            height=38,
            fg_color="#555555",
            hover_color="#444444",
            command=self.destroy
        )
        self.btn_fechar.pack(side="right")

        # Container de Resultados (Scrollable - Preenche o restante do espaço)
        self.results_container = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.results_container.pack(fill="both", expand=True, padx=25, pady=(0, 8))

    def executar_auditoria(self):
        # Limpa itens anteriores
        for widget in self.results_container.winfo_children():
            widget.destroy()

        self.lbl_status.configure(text="Executando varredura na pasta raiz de engenharia...")
        self.update_idletasks()

        problemas = self.audit_service.executar_auditoria_completa()

        if not problemas:
            self.lbl_status.configure(
                text="✓ Todos os projetos estão em conformidade com o padrão!",
                text_color="#2fa572"
            )
            card_ok = ctk.CTkFrame(self.results_container, fg_color=("#e6f4ea", "#1b3320"), corner_radius=8)
            card_ok.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(
                card_ok,
                text="✓ NENHUMA NÃO-CONFORMIDADE ENCONTRADA\n\nTodas as pastas, arquivos e estruturas estão de acordo com o padrão 000.000.",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#137333", "#81c995")
            ).pack(padx=20, pady=20)
            return

        total = len(problemas)
        self.lbl_status.configure(
            text=f"Foram encontradas {total} não-conformidades que requerem atenção:",
            text_color="#e67e22"
        )

        for p in problemas:
            self._adicionar_card_problema(p)

    def _adicionar_card_problema(self, p: ProblemaAuditoria):
        # Cores por categoria
        categoria_info = {
            "PASTA_FORA_PADRAO": ("⚠ PASTA FORA DO PADRÃO", "#d9534f"),
            "ARQUIVO_FORA_PADRAO": ("⚠ ARQUIVO FORA DO PADRÃO", "#f0ad4e"),
            "INCONSISTENCIA": ("⛔ INCONSISTÊNCIA CRÍTICA", "#d9534f"),
            "ESTRUTURA_INCOMPLETA": ("ℹ ESTRUTURA INCOMPLETA", "#0275d8"),
            "ERRO_RAIZ": ("❌ ERRO NA PASTA RAIZ", "#d9534f")
        }

        titulo_cat, cor = categoria_info.get(p.categoria, ("AVISO", "#777777"))

        card = ctk.CTkFrame(self.results_container, corner_radius=8)
        card.pack(fill="x", padx=10, pady=6)

        # Header do Card
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            top_row,
            text=titulo_cat,
            font=ctk.CTkFont(weight="bold", size=13),
            text_color=cor
        ).pack(side="left")

        # Descrição do problema
        ctk.CTkLabel(
            card,
            text=p.descricao,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            wraplength=650
        ).pack(fill="x", padx=12, pady=(2, 2))

        # Caminho
        ctk.CTkLabel(
            card,
            text=f"Local: {p.caminho}",
            font=ctk.CTkFont(size=11, family="Consolas"),
            text_color="gray",
            anchor="w",
            wraplength=650
        ).pack(fill="x", padx=12, pady=(0, 4))

        # Sugestão
        if p.sugestao:
            ctk.CTkLabel(
                card,
                text=f"Sugestão: {p.sugestao}",
                font=ctk.CTkFont(size=12),
                text_color=("#1f6aa5", "#64b5f6"),
                anchor="w",
                wraplength=650
            ).pack(fill="x", padx=12, pady=(2, 8))

        # Ações do Card
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 10))

        # Botão para abrir no Explorer
        pasta_para_abrir = p.caminho if os.path.isdir(p.caminho) else os.path.dirname(p.caminho)
        btn_abrir = ctk.CTkButton(
            btn_row,
            text="📁 Abrir Pasta",
            width=110,
            height=28,
            fg_color="#444444",
            hover_color="#333333",
            command=lambda: os.startfile(pasta_para_abrir) if os.path.exists(pasta_para_abrir) else None
        )
        btn_abrir.pack(side="left", padx=(0, 8))

        # Botão de correção automática se disponível
        if p.corrigivel:
            if p.categoria == "PASTA_FORA_PADRAO" and p.novo_caminho:
                btn_corrigir = ctk.CTkButton(
                    btn_row,
                    text="✓ Corrigir Nome da Pasta",
                    width=170,
                    height=28,
                    fg_color="#2fa572",
                    hover_color="#26865c",
                    command=lambda prob=p: self._aplicar_correcao_pasta(prob)
                )
                btn_corrigir.pack(side="left")
            elif p.categoria == "ESTRUTURA_INCOMPLETA":
                btn_criar_subs = ctk.CTkButton(
                    btn_row,
                    text="✓ Criar Subpastas Faltantes",
                    width=170,
                    height=28,
                    fg_color="#2fa572",
                    hover_color="#26865c",
                    command=lambda prob=p: self._aplicar_correcao_subpastas(prob)
                )
                btn_criar_subs.pack(side="left")

    def _aplicar_correcao_pasta(self, problema: ProblemaAuditoria):
        resp = messagebox.askyesno(
            "Confirmar Correção",
            f"Deseja renomear a pasta:\n\nDe: {os.path.basename(problema.caminho)}\nPara: {os.path.basename(problema.novo_caminho)}?",
            parent=self
        )
        if resp:
            ok, msg = self.audit_service.corrigir_pasta_automatica(problema)
            if ok:
                messagebox.showinfo("Sucesso", msg, parent=self)
                self.executar_auditoria()
            else:
                messagebox.showerror("Erro", msg, parent=self)

    def _aplicar_correcao_subpastas(self, problema: ProblemaAuditoria):
        ok, msg = self.audit_service.criar_subpastas_faltantes(problema.caminho)
        if ok:
            messagebox.showinfo("Sucesso", msg, parent=self)
            self.executar_auditoria()
        else:
            messagebox.showerror("Erro", msg, parent=self)
