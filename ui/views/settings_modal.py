"""
Modal de Configurações do Controle CAD.
Permite alterar a pasta raiz da engenharia, integrações do SolidWorks e templates.
"""

import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, Any
from core.config import carregar_config, salvar_config
from cad.solidworks_client import SolidWorksClient


class SettingsModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        sw_client: SolidWorksClient,
        on_save_callback: Callable[[Dict[str, Any]], None]
    ):
        super().__init__(parent)
        self.parent = parent
        self.sw_client = sw_client
        self.on_save = on_save_callback

        self.title("Configurações — Controle CAD")
        screen_h = self.winfo_screenheight()
        altura = min(screen_h - 100, 680)
        self.geometry(f"620x{altura}")
        self.minsize(540, 480)
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self.config_atual = carregar_config()
        self._construir_ui()

    def _construir_ui(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", side="top", padx=25, pady=(15, 6))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="CONFIGURAÇÕES DO SISTEMA",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_lbl.pack(anchor="w")

        # 2. Botões Fixos no Rodapé
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", padx=25, pady=(10, 15))

        self.btn_cancelar = ctk.CTkButton(
            btn_frame,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=38,
            command=self.destroy
        )
        self.btn_cancelar.pack(side="left")

        self.btn_salvar = ctk.CTkButton(
            btn_frame,
            text="SALVAR CONFIGURAÇÕES",
            font=ctk.CTkFont(weight="bold"),
            width=200,
            height=38,
            command=self._salvar_configuracoes
        )
        self.btn_salvar.pack(side="right")

        # 3. Formulário Central Rolável
        form_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        form_frame.pack(fill="both", expand=True, padx=25, pady=(0, 5))

        # Pasta de Engenharia
        ctk.CTkLabel(form_frame, text="Pasta Raiz de Armazenamento (Rede / SMB):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(15, 2))
        
        path_box = ctk.CTkFrame(form_frame, fg_color="transparent")
        path_box.pack(fill="x", padx=20, pady=(0, 10))

        self.entry_pasta = ctk.CTkEntry(
            path_box,
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.entry_pasta.insert(0, self.config_atual.get("pasta_raiz", ""))
        self.entry_pasta.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_buscar_pasta = ctk.CTkButton(
            path_box,
            text="BUSCAR",
            width=90,
            height=36,
            command=self._selecionar_pasta
        )
        self.btn_buscar_pasta.pack(side="right")

        # Status SolidWorks
        ctk.CTkLabel(form_frame, text="Integração SolidWorks:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(10, 2))
        
        sw_status_frame = ctk.CTkFrame(form_frame, fg_color=("#e8e8e8", "#252525"), corner_radius=6)
        sw_status_frame.pack(fill="x", padx=20, pady=(0, 15))

        status_sw_text = "SolidWorks Detectado / Conectável" if self.sw_client.esta_conectado() else "SolidWorks não conectado (Iniciará sob demanda)"
        status_color = "#2fa572" if self.sw_client.esta_conectado() else "gray"

        ctk.CTkLabel(
            sw_status_frame,
            text=f"Status: {status_sw_text}",
            font=ctk.CTkFont(size=12),
            text_color=status_color
        ).pack(anchor="w", padx=12, pady=8)

        # Switches de opções
        self.switch_sw_auto = ctk.CTkSwitch(
            form_frame,
            text="Perguntar para abrir no SolidWorks ao criar peça"
        )
        if self.config_atual.get("solidworks_automatico", True):
            self.switch_sw_auto.select()
        self.switch_sw_auto.pack(anchor="w", padx=20, pady=8)

        self.switch_pdf = ctk.CTkSwitch(
            form_frame,
            text="Geração automática de PDF (quando CAD e Desenho 2D existirem)"
        )
        if self.config_atual.get("criar_pdf", True):
            self.switch_pdf.select()
        self.switch_pdf.pack(anchor="w", padx=20, pady=8)

        self.switch_monitorar = ctk.CTkSwitch(
            form_frame,
            text="Monitorar desenhos e atualizar PDFs automaticamente em segundo plano"
        )
        if self.config_atual.get("monitorar_pasta", True):
            self.switch_monitorar.select()
        self.switch_monitorar.pack(anchor="w", padx=20, pady=8)

        self.switch_simulacao = ctk.CTkSwitch(
            form_frame,
            text="Modo Simulação SolidWorks (para testes fora do CAD)"
        )
        if self.config_atual.get("modo_simulacao_sw", False):
            self.switch_simulacao.select()
        self.switch_simulacao.pack(anchor="w", padx=20, pady=8)

        # ------------------ TEMPLATES POR LINHA DE PRODUTO ------------------
        sep_frame = ctk.CTkFrame(form_frame, height=2, fg_color=("#d0d0d0", "#3a3a3a"))
        sep_frame.pack(fill="x", padx=20, pady=(15, 12))

        ctk.CTkLabel(
            form_frame,
            text="📐 Templates de Folha de Desenho 2D (.DRWDOT) por Grupo:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#1f6aa5", "#4ea8de")
        ).pack(anchor="w", padx=20, pady=(0, 2))

        ctk.CTkLabel(
            form_frame,
            text="Ao gerar o desenho 2D de uma peça ou montagem, o template da linha selecionada será aplicado automaticamente.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=520,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Obter caminhos atuais ou auto-detectar se vazios
        mapa_linhas = self.config_atual.get("templates_desenho_linhas", {})
        if not isinstance(mapa_linhas, dict):
            mapa_linhas = {}

        def _obter_val(linha: str) -> str:
            val = mapa_linhas.get(linha, "")
            if not val or not os.path.exists(val):
                try:
                    val = self.sw_client.obter_template_desenho_por_linha(linha)
                except Exception:
                    val = ""
            return val or ""

        # 1. MedicalFix
        ctk.CTkLabel(form_frame, text="Template MedicalFix (.DRWDOT):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=20, pady=(4, 2))
        box_med = ctk.CTkFrame(form_frame, fg_color="transparent")
        box_med.pack(fill="x", padx=20, pady=(0, 8))
        self.entry_tmpl_med = ctk.CTkEntry(box_med, font=ctk.CTkFont(size=11), height=34)
        self.entry_tmpl_med.insert(0, _obter_val("MedicalFix"))
        self.entry_tmpl_med.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(box_med, text="BUSCAR", width=80, height=34, command=lambda: self._buscar_template(self.entry_tmpl_med)).pack(side="right")

        # 2. DentFix
        ctk.CTkLabel(form_frame, text="Template DentFix (.DRWDOT):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=20, pady=(4, 2))
        box_dent = ctk.CTkFrame(form_frame, fg_color="transparent")
        box_dent.pack(fill="x", padx=20, pady=(0, 8))
        self.entry_tmpl_dent = ctk.CTkEntry(box_dent, font=ctk.CTkFont(size=11), height=34)
        self.entry_tmpl_dent.insert(0, _obter_val("DentFix"))
        self.entry_tmpl_dent.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(box_dent, text="BUSCAR", width=80, height=34, command=lambda: self._buscar_template(self.entry_tmpl_dent)).pack(side="right")

        # 3. TraumaFix
        ctk.CTkLabel(form_frame, text="Template TraumaFix (.DRWDOT):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=20, pady=(4, 2))
        box_trauma = ctk.CTkFrame(form_frame, fg_color="transparent")
        box_trauma.pack(fill="x", padx=20, pady=(0, 8))
        self.entry_tmpl_trauma = ctk.CTkEntry(box_trauma, font=ctk.CTkFont(size=11), height=34)
        self.entry_tmpl_trauma.insert(0, _obter_val("TraumaFix"))
        self.entry_tmpl_trauma.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(box_trauma, text="BUSCAR", width=80, height=34, command=lambda: self._buscar_template(self.entry_tmpl_trauma)).pack(side="right")

        # Botão Auto-detectar
        ctk.CTkButton(
            form_frame,
            text="🔍 Auto-detectar Templates no SolidWorks",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#334d66",
            hover_color="#24384a",
            height=32,
            command=self._auto_detectar_templates
        ).pack(anchor="w", padx=20, pady=(4, 15))

    def _buscar_template(self, entry_widget: ctk.CTkEntry):
        caminho_inicial = os.path.dirname(entry_widget.get().strip()) if entry_widget.get().strip() else r"C:\CONFIGURAÇÕES SOLIDWORKS"
        if not os.path.exists(caminho_inicial):
            caminho_inicial = r"C:\\"
        caminho = filedialog.askopenfilename(
            title="Selecionar Template de Desenho 2D (.DRWDOT)",
            initialdir=caminho_inicial,
            filetypes=[
                ("Templates de Desenho SolidWorks (*.DRWDOT;*.drwdot)", "*.DRWDOT;*.drwdot"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if caminho:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, os.path.normpath(caminho))

    def _auto_detectar_templates(self):
        """Varre os diretórios do SolidWorks e preenche os campos automaticamente."""
        achou_algum = False
        for linha, entry in [("MedicalFix", self.entry_tmpl_med), ("DentFix", self.entry_tmpl_dent), ("TraumaFix", self.entry_tmpl_trauma)]:
            try:
                tmpl = self.sw_client.obter_template_desenho_por_linha(linha)
                if tmpl and os.path.exists(tmpl):
                    entry.delete(0, "end")
                    entry.insert(0, os.path.normpath(tmpl))
                    achou_algum = True
            except Exception:
                pass

        if achou_algum:
            messagebox.showinfo("Auto-Detecção", "Templates localizados e atualizados nos campos com sucesso!", parent=self)
        else:
            messagebox.showwarning("Auto-Detecção", "Não foram localizados templates automáticos nos diretórios padrão do SolidWorks.", parent=self)

    def _selecionar_pasta(self):
        caminho = filedialog.askdirectory(
            title="Selecione a Pasta Raiz de Engenharia",
            initialdir=self.entry_pasta.get()
        )
        if caminho:
            self.entry_pasta.delete(0, "end")
            self.entry_pasta.insert(0, os.path.normpath(caminho))

    def _salvar_configuracoes(self):
        pasta_nova = self.entry_pasta.get().strip()
        if not pasta_nova:
            messagebox.showerror("Erro", "A pasta de engenharia não pode ser vazia.", parent=self)
            return

        if not os.path.exists(pasta_nova):
            criar = messagebox.askyesno(
                "Criar Pasta",
                f"A pasta '{pasta_nova}' não existe.\nDeseja criá-la agora?",
                parent=self
            )
            if criar:
                try:
                    os.makedirs(pasta_nova, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Erro", f"Não foi possível criar a pasta: {e}", parent=self)
                    return
            else:
                return

        novas_configs = {
            "pasta_raiz": pasta_nova,
            "solidworks_automatico": bool(self.switch_sw_auto.get()),
            "criar_pdf": bool(self.switch_pdf.get()),
            "modo_simulacao_sw": bool(self.switch_simulacao.get()),
            "monitorar_pasta": bool(self.switch_monitorar.get()),
            "template_peca": self.config_atual.get("template_peca", ""),
            "template_montagem": self.config_atual.get("template_montagem", ""),
            "template_desenho": self.config_atual.get("template_desenho", ""),
            "templates_desenho_linhas": {
                "MedicalFix": self.entry_tmpl_med.get().strip(),
                "DentFix": self.entry_tmpl_dent.get().strip(),
                "TraumaFix": self.entry_tmpl_trauma.get().strip()
            }
        }

        if salvar_config(novas_configs):
            self.sw_client.modo_simulacao = novas_configs["modo_simulacao_sw"]
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!", parent=self)
            self.on_save(novas_configs)
            self.destroy()
        else:
            messagebox.showerror("Erro", "Falha ao salvar o arquivo config.json.", parent=self)
