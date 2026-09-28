"""
Modal de Criação de Nova Peça no Controle CAD.
Implementa validações estritas de código, nome, checagem de código duplicado,
alerta de nomes semelhantes e abertura automática no SolidWorks.
"""

import os
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional, List
from core.models import PecaInfo, ComponenteItem, LINHAS_PRODUTO
from core.validator import validar_codigo, validar_nome_peca
from services.storage_service import StorageService
from services.duplicate_service import DuplicateService
from cad.solidworks_client import SolidWorksClient
from ui.views.select_components_modal import SelectComponentsModal


class NewPartModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        storage_service: StorageService,
        duplicate_service: DuplicateService,
        sw_client: SolidWorksClient,
        on_success_callback: Callable[[PecaInfo], None]
    ):
        super().__init__(parent)
        self.parent = parent
        self.storage = storage_service
        self.duplicate = duplicate_service
        self.sw_client = sw_client
        self.on_success = on_success_callback
        self.componentes_selecionados: List[ComponenteItem] = []

        self.title("Nova Peça — Controle CAD")
        screen_h = self.winfo_screenheight()
        altura_inicial = min(screen_h - 100, 680)
        self.geometry(f"540x{altura_inicial}")
        self.minsize(480, 440)
        self.resizable(True, True)
        self.grab_set()  # Modal bloqueante

        # Centraliza na janela pai
        self.transient(parent)
        self._construir_ui()

    def _construir_ui(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", side="top", padx=25, pady=(15, 6))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="CADASTRO DE NOVA PEÇA",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="Preencha os dados da peça para criar a estrutura padronizada.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc_lbl.pack(anchor="w")

        # 2. Botões de Ação Fixos no Rodapé (Garante que nunca fiquem invisíveis)
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

        self.btn_continuar = ctk.CTkButton(
            btn_frame,
            text="CONTINUAR ➔",
            font=ctk.CTkFont(weight="bold"),
            width=160,
            height=38,
            command=self._processar_cadastro
        )
        self.btn_continuar.pack(side="right")

        # 3. Formulário Central Rolável (Adapta-se a qualquer resolução de tela)
        form_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        form_frame.pack(fill="both", expand=True, padx=25, pady=(0, 5))

        # Banner de atalho para importar arquivos prontos
        banner_import = ctk.CTkFrame(form_frame, fg_color=("#fff3cd", "#282318"), corner_radius=8, border_width=1, border_color="#e0a96d")
        banner_import.pack(fill="x", padx=20, pady=(10, 8))

        linha_banner = ctk.CTkFrame(banner_import, fg_color="transparent")
        linha_banner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            linha_banner,
            text="💡 Já possui arquivos 3D ou 2D prontos?",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#856404", "#f1c40f")
        ).pack(side="left")

        btn_ir_import = ctk.CTkButton(
            linha_banner,
            text="📥 Importar Arquivos Prontos...",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#d9822b",
            hover_color="#b8691b",
            command=self._abrir_importacao_prontos
        )
        btn_ir_import.pack(side="right")

        # Campo Linha de Produto
        ctk.CTkLabel(form_frame, text="Linha de Produto:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(8, 2))
        self.combo_linha = ctk.CTkComboBox(
            form_frame,
            values=LINHAS_PRODUTO,
            state="readonly",
            height=38,
            font=ctk.CTkFont(size=13),
            command=self._ao_mudar_linha
        )
        self.combo_linha.set("MedicalFix")
        self.combo_linha.pack(fill="x", padx=20, pady=(0, 10))

        # Campo Tipo
        ctk.CTkLabel(form_frame, text="Tipo de Documento:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(8, 2))
        self.combo_tipo = ctk.CTkComboBox(
            form_frame,
            values=["Peça", "Montagem", "CO"],
            state="readonly",
            height=38,
            font=ctk.CTkFont(size=13),
            command=self._ao_mudar_tipo
        )
        self.combo_tipo.set("Peça")
        self.combo_tipo.pack(fill="x", padx=20, pady=(0, 10))

        # Campo Código
        self.lbl_codigo_titulo = ctk.CTkLabel(
            form_frame,
            text="Código da Peça (000.000):",
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_codigo_titulo.pack(anchor="w", padx=20, pady=(5, 2))
        self.entry_codigo = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: 250.001",
            font=ctk.CTkFont(size=14, family="Consolas"),
            height=38
        )
        self.entry_codigo.pack(fill="x", padx=20, pady=(0, 2))
        self.lbl_codigo_hint = ctk.CTkLabel(
            form_frame,
            text="Formato obrigatório: 3 números, ponto, 3 números (000.000)",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.lbl_codigo_hint.pack(anchor="w", padx=20, pady=(0, 10))

        # Campo Nome
        self.lbl_nome_titulo = ctk.CTkLabel(form_frame, text="Nome da Peça:", font=ctk.CTkFont(weight="bold"))
        self.lbl_nome_titulo.pack(anchor="w", padx=20, pady=(5, 2))
        self.entry_nome = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: Parafuso ou Suporte Motor",
            font=ctk.CTkFont(size=13),
            height=38
        )
        self.entry_nome.pack(fill="x", padx=20, pady=(0, 10))

        # Campo Descrição
        ctk.CTkLabel(form_frame, text="Descrição Detalhada:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.entry_descricao = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: Parafuso sextavado M8 x 30",
            font=ctk.CTkFont(size=13),
            height=38
        )
        self.entry_descricao.pack(fill="x", padx=20, pady=(0, 10))

        # Campo Kits
        ctk.CTkLabel(form_frame, text="Kits (opcional, separados por vírgula):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        linha_kits = ctk.CTkFrame(form_frame, fg_color="transparent")
        linha_kits.pack(fill="x", padx=20, pady=(0, 10))

        self.entry_kits = ctk.CTkEntry(
            linha_kits,
            placeholder_text="Ex: Kit Cirúrgico, Kit Implante",
            font=ctk.CTkFont(size=13),
            height=38
        )
        self.entry_kits.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_escolher_kits = ctk.CTkButton(
            linha_kits,
            text="🏷️ Escolher...",
            width=110,
            height=38,
            fg_color="#334d66",
            hover_color="#24384a",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._abrir_seletor_kits_cadastrados
        )
        self.btn_escolher_kits.pack(side="right")

        # Frame de Componentes para Montagem (visível apenas quando tipo == "Montagem")
        self.frame_componentes_montagem = ctk.CTkFrame(form_frame, fg_color=("#ebebeb", "#20242b"), corner_radius=8)
        
        lbl_comp_tit = ctk.CTkLabel(
            self.frame_componentes_montagem,
            text="📦 Componentes da Montagem (CO):",
            font=ctk.CTkFont(weight="bold", size=12)
        )
        lbl_comp_tit.pack(anchor="w", padx=12, pady=(8, 2))

        linha_comp = ctk.CTkFrame(self.frame_componentes_montagem, fg_color="transparent")
        linha_comp.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_componentes_status = ctk.CTkLabel(
            linha_comp,
            text="Nenhum componente selecionado",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.lbl_componentes_status.pack(side="left", fill="x", expand=True)

        self.btn_selecionar_cos = ctk.CTkButton(
            linha_comp,
            text="🔍 Selecionar COs...",
            width=140,
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._abrir_modal_selecao_cos
        )
        self.btn_selecionar_cos.pack(side="right")

    def _ao_mudar_linha(self, valor: str):
        """Ao alterar a linha de produto, atualiza o contexto."""
        pass

    def _ao_mudar_tipo(self, valor: str):
        if valor.upper() == "CO":
            self.lbl_codigo_titulo.configure(text="Código do Componente (CO-0000):")
            self.entry_codigo.configure(placeholder_text="Ex: CO-0001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório para Componente: CO-0000 (ex: CO-0001)")
            self.lbl_nome_titulo.configure(text="Nome do Componente:")
            self.frame_componentes_montagem.pack_forget()
        elif valor.upper() == "MONTAGEM":
            self.lbl_codigo_titulo.configure(text="Código da Montagem (000.000):")
            self.entry_codigo.configure(placeholder_text="Ex: 250.001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório: 3 números, ponto, 3 números (000.000)")
            self.lbl_nome_titulo.configure(text="Nome da Montagem:")
            # Exibe painel de seleção de componentes dentro do formulário rolável
            self.frame_componentes_montagem.pack(fill="x", padx=20, pady=(0, 15))
            self._atualizar_label_componentes()
        else:
            self.lbl_codigo_titulo.configure(text=f"Código da {valor} (000.000):")
            self.entry_codigo.configure(placeholder_text="Ex: 250.001")
            self.lbl_codigo_hint.configure(text="Formato obrigatório: 3 números, ponto, 3 números (000.000)")
            self.lbl_nome_titulo.configure(text=f"Nome da {valor}:")
            self.frame_componentes_montagem.pack_forget()

    def _atualizar_label_componentes(self):
        total = len(self.componentes_selecionados)
        if total == 0:
            self.lbl_componentes_status.configure(
                text="Nenhum componente selecionado",
                text_color="gray"
            )
        else:
            amostra = ", ".join([f"{c.codigo} (x{c.quantidade})" for c in self.componentes_selecionados[:2]])
            if total > 2:
                amostra += f" +{total - 2}"
            self.lbl_componentes_status.configure(
                text=f"✓ {total} CO(s): {amostra}",
                text_color=("#1f6aa5", "#64b5f6")
            )

    def _abrir_modal_selecao_cos(self, continuar_apos_confirmacao=False):
        def _ao_confirmar(componentes: List[ComponenteItem]):
            self.componentes_selecionados = componentes
            self._atualizar_label_componentes()
            if continuar_apos_confirmacao:
                self._executar_criacao_projeto()

        SelectComponentsModal(
            parent=self,
            storage_service=self.storage,
            on_confirm_callback=_ao_confirmar,
            componentes_iniciais=self.componentes_selecionados,
            codigo_montagem=self.entry_codigo.get().strip(),
            nome_montagem=self.entry_nome.get().strip()
        )

    def _abrir_seletor_kits_cadastrados(self):
        """Abre uma janela para marcar os kits da linha de produto selecionada ou cadastrar um novo."""
        linha_atual = self.combo_linha.get()
        texto_atual = self.entry_kits.get().strip()
        kits_ja_digitados = {k.strip().lower(): k.strip() for k in texto_atual.split(",") if k.strip()}

        popup = ctk.CTkToplevel(self)
        popup.title(f"Selecionar Kits — {linha_atual}")
        popup.geometry("450x510")
        popup.minsize(400, 440)
        popup.grab_set()
        popup.transient(self)

        ctk.CTkLabel(
            popup,
            text=f"🏷️ SELECIONAR KITS — {linha_atual.upper()}",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 2))

        ctk.CTkLabel(
            popup,
            text=f"Linha de produto: {linha_atual}. Marque os kits aos quais este item pertence:",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 8))

        # Filtro de exibição na janela popup
        frame_filtro = ctk.CTkFrame(popup, fg_color="transparent")
        frame_filtro.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(frame_filtro, text="Filtrar:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        combo_filtro_popup = ctk.CTkComboBox(
            frame_filtro,
            values=[f"Apenas Linha {linha_atual}", "Todas as Linhas"],
            state="readonly",
            height=30,
            font=ctk.CTkFont(size=11),
            width=210
        )
        combo_filtro_popup.set(f"Apenas Linha {linha_atual}")
        combo_filtro_popup.pack(side="left")

        scroll = ctk.CTkScrollableFrame(popup, height=220, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        chk_vars = {}

        def _recarregar_lista_kits(*args):
            for w in scroll.winfo_children():
                w.destroy()

            filtro_sel = combo_filtro_popup.get()
            if filtro_sel.startswith("Apenas"):
                kits_exibir = self.storage.obter_todos_kits(linha=linha_atual)
            else:
                kits_exibir = self.storage.obter_todos_kits()

            # Garante que kits que já estavam marcados não desapareçam da tela
            for k_nome, v in list(chk_vars.items()):
                if v.get() and k_nome not in kits_exibir:
                    kits_exibir.append(k_nome)

            if not kits_exibir:
                ctk.CTkLabel(
                    scroll,
                    text=f"Nenhum kit cadastrado para a linha '{linha_atual}' ainda.\n"
                         "Você pode cadastrar um kit abaixo ou mudar para 'Todas as Linhas'.",
                    font=ctk.CTkFont(size=11),
                    text_color="gray",
                    justify="center"
                ).pack(pady=25)
                return

            for kit_nome in kits_exibir:
                if kit_nome not in chk_vars:
                    chk_vars[kit_nome] = ctk.BooleanVar(value=(kit_nome.lower() in kits_ja_digitados))
                var = chk_vars[kit_nome]

                linha = ctk.CTkFrame(scroll, fg_color="transparent")
                linha.pack(fill="x", pady=2)
                ctk.CTkCheckBox(
                    linha,
                    text=f"🏷️  {kit_nome}",
                    variable=var,
                    font=ctk.CTkFont(size=12)
                ).pack(side="left", padx=5)

        combo_filtro_popup.configure(command=lambda _: _recarregar_lista_kits())
        _recarregar_lista_kits()

        # Entrada para novo kit rápido vinculado à linha atual
        frame_novo = ctk.CTkFrame(popup, fg_color="transparent")
        frame_novo.pack(fill="x", padx=20, pady=(0, 10))

        entry_novo_kit = ctk.CTkEntry(
            frame_novo,
            placeholder_text=f"Novo kit na linha {linha_atual}...",
            height=32,
            font=ctk.CTkFont(size=11)
        )
        entry_novo_kit.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _adicionar_kit_rapido():
            novo = entry_novo_kit.get().strip()
            if novo:
                ok, _ = self.storage.cadastrar_kit(novo, linha=linha_atual)
                chk_vars[novo] = ctk.BooleanVar(value=True)
                entry_novo_kit.delete(0, "end")
                _recarregar_lista_kits()

        entry_novo_kit.bind("<Return>", lambda e: _adicionar_kit_rapido())

        ctk.CTkButton(
            frame_novo,
            text="+ Add",
            width=60,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=_adicionar_kit_rapido
        ).pack(side="right")

        def _confirmar():
            selecionados = [k for k, v in chk_vars.items() if v.get()]
            for k_manual in kits_ja_digitados.values():
                if not any(k.lower() == k_manual.lower() for k in chk_vars) and k_manual not in selecionados:
                    selecionados.append(k_manual)
            self.entry_kits.delete(0, "end")
            self.entry_kits.insert(0, ", ".join(selecionados))
            popup.destroy()

        btn_box = ctk.CTkFrame(popup, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkButton(
            btn_box,
            text="CONFIRMAR",
            font=ctk.CTkFont(weight="bold"),
            height=36,
            command=_confirmar
        ).pack(fill="x")

    def _processar_cadastro(self):
        codigo = self.entry_codigo.get().strip()
        nome = self.entry_nome.get().strip()
        tipo = self.combo_tipo.get()

        if tipo.upper() == "CO":
            codigo = codigo.upper()

        # 1. Validação estrita do código
        val_cod, msg_cod = validar_codigo(codigo, tipo=tipo)
        if not val_cod:
            messagebox.showerror("Código Inválido", msg_cod, parent=self)
            self.entry_codigo.focus()
            return

        # 2. Validação do nome
        val_nome, msg_nome = validar_nome_peca(nome)
        if not val_nome:
            messagebox.showerror("Nome Inválido", msg_nome, parent=self)
            self.entry_nome.focus()
            return

        # 3. Verificação de Código Duplicado (Bloqueio estrito)
        peca_existente = self.duplicate.verificar_codigo_existente(codigo)
        if peca_existente:
            msg = (
                f"⚠ CÓDIGO JÁ EXISTENTE\n\n"
                f"{peca_existente.codigo} - {peca_existente.nome}\n"
                f"Revisão atual: {peca_existente.revisao_atual}\n\n"
                f"Esta peça já está cadastrada e não pode ser criada novamente."
            )
            resposta = messagebox.askyesno(
                "Código Duplicado",
                f"{msg}\n\nDeseja abrir a pasta da peça existente?",
                parent=self
            )
            if resposta and os.path.exists(peca_existente.pasta_path):
                os.startfile(peca_existente.pasta_path)
            return

        # 4. Verificação de Nomes Semelhantes (Alerta consultivo)
        semelhantes = self.duplicate.buscar_nomes_semelhantes(nome, limiar_similaridade=0.55)
        if semelhantes:
            itens_str = "\n".join([f"• {p.codigo} - {p.nome} (Rev {p.revisao_atual})" for p, _ in semelhantes[:4]])
            msg_semelhantes = (
                f"⚠ POSSÍVEIS PEÇAS SEMELHANTES ENCONTRADAS\n\n"
                f"Foram encontradas peças com nomes similares já cadastradas:\n"
                f"{itens_str}\n\n"
                f"Verifique se alguma dessas peças existentes pode ser reutilizada.\n\n"
                f"Deseja criar a nova peça mesmo assim?"
            )
            criar_mesmo_assim = messagebox.askyesno(
                "Possível Duplicidade de Nome",
                msg_semelhantes,
                parent=self
            )
            if not criar_mesmo_assim:
                return

        # 5. Se for Montagem e nenhum CO tiver sido selecionado ainda, pergunta ao usuário
        if tipo.upper() == "MONTAGEM" and not self.componentes_selecionados:
            resposta_cos = messagebox.askyesnocancel(
                "Componentes da Montagem (CO)",
                f"Esta é uma Montagem ({codigo} - {nome}).\n\n"
                f"A montagem é formada por vários componentes comerciais (CO) comprados.\n\n"
                f"Deseja selecionar quais COs fazem parte desta montagem agora?",
                parent=self
            )
            if resposta_cos is None:
                # Cancelou o fluxo
                return
            elif resposta_cos is True:
                # Abre o modal de seleção e prossegue automaticamente após confirmação
                self._abrir_modal_selecao_cos(continuar_apos_confirmacao=True)
                return

        # Prossegue com a criação
        self._executar_criacao_projeto()

    def _executar_criacao_projeto(self):
        codigo = self.entry_codigo.get().strip()
        nome = self.entry_nome.get().strip()
        tipo = self.combo_tipo.get()
        descricao = self.entry_descricao.get().strip() or nome

        kits_str = self.entry_kits.get().strip()
        kits_list = [k.strip() for k in kits_str.split(",") if k.strip()] if kits_str else []

        if tipo.upper() == "CO":
            codigo = codigo.upper()

        linha_escolhida = self.combo_linha.get()

        # Criação da Estrutura de Pastas e controle.json
        nova_peca = PecaInfo(
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            tipo=tipo,
            revisao_atual="A",
            componentes=self.componentes_selecionados,
            kits=kits_list,
            linha_produto=linha_escolhida
        )

        sucesso, msg_res = self.storage.criar_estrutura_peca(nova_peca)
        if not sucesso:
            messagebox.showerror("Erro ao Criar Pasta", msg_res, parent=self)
            return

        # Diálogo de Integração com SolidWorks
        rotulo_tipo = "COMPONENTE (CO)" if tipo.upper() == "CO" else ("MONTAGEM" if tipo.upper() == "MONTAGEM" else "PEÇA")
        info_componentes = ""
        if self.componentes_selecionados:
            info_componentes = f"Componentes vinculados: {len(self.componentes_selecionados)} CO(s)\n"

        msg_sucesso = (
            f"✓ {rotulo_tipo} CRIADO COM SUCESSO\n\n"
            f"Linha de Produto: {linha_escolhida}\n"
            f"Código: {codigo}\n"
            f"Nome: {nome}\n"
            f"Tipo: {tipo}\n"
            f"Revisão inicial: A\n"
            f"{info_componentes}\n"
            f"Deseja abrir e criar o arquivo no SolidWorks agora?"
        )
        abrir_sw = messagebox.askyesno(
            "Abrir no SolidWorks?",
            msg_sucesso,
            parent=self
        )

        if abrir_sw:
            # Caminhos de destino para o modelo CAD e desenho 2D
            ext = ".SLDASM" if tipo == "Montagem" else ".SLDPRT"
            caminho_cad = self.storage.obter_pasta_peca(codigo, nome)
            caminho_arquivo_cad = os.path.join(caminho_cad, "CAD", f"{codigo}{ext}")
            caminho_arquivo_desenho = os.path.join(caminho_cad, "DESENHO", f"{codigo}.SLDDRW")

            # 1. Cria e salva o modelo 3D (com os componentes vinculados)
            ok_sw, msg_sw = self.sw_client.criar_novo_documento_cad(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                caminho_salvar=caminho_arquivo_cad,
                componentes=self.componentes_selecionados
            )
            
            # 2. Cria e salva o desenho 2D automaticamente (vinculado ao modelo)
            ok_drw, msg_drw = self.sw_client.criar_novo_desenho_cad(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                caminho_salvar_desenho=caminho_arquivo_desenho,
                caminho_modelo_cad=caminho_arquivo_cad
            )

            if not ok_sw:
                messagebox.showwarning("Aviso SolidWorks", msg_sw, parent=self)
            else:
                msg_final = (
                    f"✓ PROJETO CONFIGURADO COM SUCESSO NO SOLIDWORKS\n\n"
                    f"• Modelo 3D: CAD\\{codigo}{ext}\n"
                    f"• Desenho 2D: DESENHO\\{codigo}.SLDDRW\n\n"
                    f"Ambos os arquivos já foram salvos e vinculados aos seus locais definitivos.\n"
                    f"Ao salvar (Ctrl+S) no SolidWorks, ele salvará automaticamente sem pedir pastas."
                )
                messagebox.showinfo("SolidWorks", msg_final, parent=self)

        # Notifica a janela principal e fecha
        self.on_success(nova_peca)
        self.destroy()

    def _abrir_importacao_prontos(self):
        """Redireciona para o modal de importação de arquivos prontos."""
        from ui.views.import_parts_modal import ImportPartsModal
        self.destroy()
        ImportPartsModal(
            parent=self.parent,
            storage_service=self.storage,
            on_success_callback=self.on_success,
            sw_client=self.sw_client
        )
