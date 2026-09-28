"""
Modal de Nova Revisão do Controle CAD.
Garante o registro obrigatório do motivo da alteração e arquiva a revisão anterior.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Callable
from core.models import PecaInfo
from core.validator import proxima_revisao
from services.revision_service import RevisionService
from services.storage_service import StorageService
from cad.solidworks_client import SolidWorksClient


class NewRevisionModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        peca: PecaInfo,
        revision_service: RevisionService,
        storage_service: StorageService,
        sw_client: SolidWorksClient,
        on_success_callback: Callable[[PecaInfo], None]
    ):
        super().__init__(parent)
        self.parent = parent
        self.peca = peca
        self.revision_service = revision_service
        self.storage = storage_service
        self.sw_client = sw_client
        self.on_success = on_success_callback

        self.nova_rev = proxima_revisao(self.peca.revisao_atual)

        self.title("Nova Revisão — Controle CAD")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        altura = min(sh - 80, 530)
        largura = min(sw - 40, 520)
        self.geometry(f"{largura}x{altura}")
        self.minsize(460, 420)
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._construir_ui()

    def _construir_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(20, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="CRIAR NOVA REVISÃO",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="Os arquivos atuais serão copiados para o histórico antes da alteração.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc_lbl.pack(anchor="w")

        # Botões Rodapé (Dockado no fundo para nunca ser ocultado)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(10, 20), side="bottom")

        self.btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=40,
            command=self.destroy
        )
        self.btn_cancelar.pack(side="left")

        self.btn_confirmar = ctk.CTkButton(
            btn_frame,
            text=f"CONFIRMAR REV {self.nova_rev} ✓",
            font=ctk.CTkFont(weight="bold"),
            width=180,
            height=40,
            command=self._processar_revisao
        )
        self.btn_confirmar.pack(side="right")

        # Dados da Peça
        info_frame = ctk.CTkFrame(self, corner_radius=10)
        info_frame.pack(fill="x", padx=25, pady=10)

        ctk.CTkLabel(
            info_frame,
            text=f"Peça: {self.peca.codigo} - {self.peca.nome}",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 6))

        rev_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        rev_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(
            rev_frame,
            text=f"Revisão Atual: {self.peca.revisao_atual}",
            font=ctk.CTkFont(size=13)
        ).pack(side="left")

        ctk.CTkLabel(
            rev_frame,
            text=" ➔ ",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1f6aa5"
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            rev_frame,
            text=f"Nova Revisão: {self.nova_rev}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#2fa572"
        ).pack(side="left")

        # Campo Motivo da Alteração
        motivo_frame = ctk.CTkFrame(self, corner_radius=10)
        motivo_frame.pack(fill="both", expand=True, padx=25, pady=10)

        ctk.CTkLabel(
            motivo_frame,
            text="Motivo da Alteração (Obrigatório):",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 5))

        self.txt_motivo = ctk.CTkTextbox(
            motivo_frame,
            font=ctk.CTkFont(size=13),
            height=120
        )
        self.txt_motivo.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.txt_motivo.focus()

    def _processar_revisao(self):
        motivo = self.txt_motivo.get("1.0", "end-1c").strip()
        if not motivo:
            messagebox.showwarning(
                "Motivo Obrigatório",
                "Por favor, informe detalhadamente o motivo da nova revisão.",
                parent=self
            )
            self.txt_motivo.focus()
            return

        # Executa a revisão no sistema de arquivos e controle.json
        sucesso, nova_rev, msg = self.revision_service.criar_nova_revisao(
            peca=self.peca,
            motivo=motivo
        )

        if not sucesso:
            messagebox.showerror("Erro de Revisão", msg, parent=self)
            return

        # Atualiza a propriedade REVISAO no arquivo CAD se existir
        caminho_cad = self.storage.obter_caminho_cad(self.peca)
        if caminho_cad:
            ok_sw, msg_sw = self.sw_client.atualizar_revisao_no_arquivo(caminho_cad, nova_rev)
            if not ok_sw:
                print(f"Aviso de propriedade CAD: {msg_sw}")

        messagebox.showinfo(
            "Revisão Criada",
            f"✓ Revisão {nova_rev} criada com sucesso!\n\n"
            f"A versão anterior (Rev {self.peca.historico[-2].revisao if len(self.peca.historico) > 1 else 'A'}) "
            f"foi arquivada na pasta HISTORICO.\n"
            f"O arquivo de trabalho ativo permanece com o mesmo nome na pasta CAD.",
            parent=self
        )

        self.on_success(self.peca)
        self.destroy()
