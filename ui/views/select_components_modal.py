"""
Modal para Seleção de Componentes (CO) de uma Montagem no Controle CAD.
Permite selecionar quais COs comprados fazem parte da montagem e suas respectivas quantidades.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import List, Callable, Optional, Dict
from core.models import ComponenteItem, PecaInfo
from core.validator import validar_codigo
from services.storage_service import StorageService


class SelectComponentsModal(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        storage_service: StorageService,
        on_confirm_callback: Callable[[List[ComponenteItem]], None],
        componentes_iniciais: Optional[List[ComponenteItem]] = None,
        codigo_montagem: str = "",
        nome_montagem: str = ""
    ):
        super().__init__(parent)
        self.parent = parent
        self.storage = storage_service
        self.on_confirm = on_confirm_callback
        self.codigo_montagem = codigo_montagem
        self.nome_montagem = nome_montagem

        # Mapa de estado dos componentes: codigo -> {"nome": str, "check_var": BooleanVar, "qtd_entry": CTkEntry}
        self.itens_estado: Dict[str, dict] = {}
        # Componentes manuais adicionados
        self.componentes_manuais: List[ComponenteItem] = []

        # Inicializa lista existente
        self.componentes_iniciais_map: Dict[str, ComponenteItem] = {}
        if componentes_iniciais:
            for c in componentes_iniciais:
                self.componentes_iniciais_map[c.codigo.upper()] = c

        self.title("Componentes da Montagem (CO) — Controle CAD")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        largura = min(sw - 40, 680)
        altura = min(sh - 80, 680)
        self.geometry(f"{largura}x{altura}")
        self.minsize(560, 450)
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._construir_ui()
        self._carregar_lista_cos()

    def _construir_ui(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(16, 8))

        titulo_texto = "COMPONENTES DA MONTAGEM (CO)"
        if self.codigo_montagem:
            titulo_texto += f" — {self.codigo_montagem}"

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text=titulo_texto,
            font=ctk.CTkFont(size=17, weight="bold")
        )
        lbl_titulo.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            header_frame,
            text="Selecione os componentes comerciais (CO) que compõem esta montagem e defina as quantidades:",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        lbl_desc.pack(anchor="w", pady=(2, 0))

        # 2. Rodapé com Resumo e Botões de Ação (Dockado no fundo para sempre estar visível)
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=25, pady=(5, 15), side="bottom")

        self.lbl_resumo_selecao = ctk.CTkLabel(
            footer_frame,
            text="0 componentes selecionados (0 unidades no total)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.lbl_resumo_selecao.pack(anchor="w", pady=(0, 8))

        btn_acoes = ctk.CTkFrame(footer_frame, fg_color="transparent")
        btn_acoes.pack(fill="x")

        self.btn_cancelar = ctk.CTkButton(
            btn_acoes,
            text="CANCELAR",
            fg_color="#555555",
            hover_color="#444444",
            width=120,
            height=38,
            command=self.destroy
        )
        self.btn_cancelar.pack(side="left")

        self.btn_confirmar = ctk.CTkButton(
            btn_acoes,
            text="CONFIRMAR COMPONENTES ➔",
            font=ctk.CTkFont(weight="bold"),
            width=220,
            height=38,
            command=self._confirmar_selecao
        )
        self.btn_confirmar.pack(side="right")

        # 3. Seção de Adicionar CO Manual (Dockado acima do rodapé)
        add_manual_frame = ctk.CTkFrame(self, corner_radius=8, fg_color=("#ebebeb", "#23272e"))
        add_manual_frame.pack(fill="x", padx=25, pady=(0, 10), side="bottom")

        lbl_manual = ctk.CTkLabel(
            add_manual_frame,
            text="+ Inserir outro CO não listado:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_manual.pack(anchor="w", padx=12, pady=(6, 4))

        linha_manual = ctk.CTkFrame(add_manual_frame, fg_color="transparent")
        linha_manual.pack(fill="x", padx=12, pady=(0, 8))

        self.entry_manual_cod = ctk.CTkEntry(
            linha_manual,
            placeholder_text="Código (ex: CO-0010)",
            font=ctk.CTkFont(size=12, family="Consolas"),
            width=150,
            height=32
        )
        self.entry_manual_cod.pack(side="left", padx=(0, 8))

        self.entry_manual_nome = ctk.CTkEntry(
            linha_manual,
            placeholder_text="Descrição (ex: Anel O-ring 25x3)",
            font=ctk.CTkFont(size=12),
            height=32
        )
        self.entry_manual_nome.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.entry_manual_qtd = ctk.CTkEntry(
            linha_manual,
            placeholder_text="Qtd",
            font=ctk.CTkFont(size=12),
            width=50,
            height=32
        )
        self.entry_manual_qtd.insert(0, "1")
        self.entry_manual_qtd.pack(side="left", padx=(0, 8))

        btn_add_manual = ctk.CTkButton(
            linha_manual,
            text="+ Adicionar",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=90,
            height=32,
            fg_color="#d9822b",
            hover_color="#b8691b",
            command=self._adicionar_co_manual
        )
        btn_add_manual.pack(side="left")

        # 4. Barra de Busca e Ação
        busca_frame = ctk.CTkFrame(self, fg_color="transparent")
        busca_frame.pack(fill="x", padx=25, pady=(4, 8))

        self.entry_busca = ctk.CTkEntry(
            busca_frame,
            placeholder_text="🔎 Pesquisar CO por código ou descrição...",
            font=ctk.CTkFont(size=13),
            height=36
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_busca.bind("<KeyRelease>", lambda e: self._filtrar_exibicao())

        btn_limpar_busca = ctk.CTkButton(
            busca_frame,
            text="Limpar",
            width=70,
            height=36,
            fg_color="#555555",
            hover_color="#444444",
            command=self._limpar_busca
        )
        btn_limpar_busca.pack(side="left")

        # 5. Lista Rolável de Componentes (Ocupa todo o espaço restante)
        self.scroll_lista = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.scroll_lista.pack(fill="both", expand=True, padx=25, pady=(0, 8))

    def _limpar_busca(self):
        self.entry_busca.delete(0, "end")
        self._filtrar_exibicao()

    def _carregar_lista_cos(self):
        # Busca todas as peças cadastradas do tipo CO
        cos_cadastrados = self.storage.obter_todos_cos()
        self.todos_cos_info = cos_cadastrados

        # Também adiciona itens pré-existentes na montagem que possam não estar na pasta
        for cod_init, item_init in self.componentes_iniciais_map.items():
            ja_esta = any(p.codigo.upper() == cod_init for p in self.todos_cos_info)
            if not ja_esta:
                self.componentes_manuais.append(item_init)

        self._renderizar_itens()

    def _renderizar_itens(self):
        for w in self.scroll_lista.winfo_children():
            w.destroy()

        termo = self.entry_busca.get().strip().lower()

        # Combina COs cadastrados com COs manuais
        itens_para_exibir: List[tuple] = []
        for p in self.todos_cos_info:
            itens_para_exibir.append((p.codigo, p.nome, False))
        for m in self.componentes_manuais:
            itens_para_exibir.append((m.codigo, m.nome, True))

        # Remove duplicatas de exibição
        vistos = set()
        itens_unicos = []
        for cod, nome, is_manual in itens_para_exibir:
            cod_u = cod.upper()
            if cod_u not in vistos:
                vistos.add(cod_u)
                itens_unicos.append((cod, nome, is_manual))

        itens_filtrados = [
            (c, n, m) for c, n, m in itens_unicos
            if not termo or (termo in c.lower() or termo in n.lower())
        ]

        if not itens_filtrados:
            msg = "Nenhum componente (CO) encontrado." if self.todos_cos_info or self.componentes_manuais else "Nenhum CO cadastrado ainda. Use o campo abaixo para adicionar manualmente."
            ctk.CTkLabel(
                self.scroll_lista,
                text=msg,
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack(pady=30)
            self._atualizar_resumo()
            return

        for idx, (cod, nome, is_manual) in enumerate(itens_filtrados):
            cod_upper = cod.upper()
            row_frame = ctk.CTkFrame(
                self.scroll_lista,
                fg_color=("#f9f9f9", "#1e2228") if idx % 2 == 0 else ("#f0f0f0", "#181a1f"),
                corner_radius=6,
                height=42
            )
            row_frame.pack(fill="x", pady=2, padx=4)

            # Estado atual do item
            if cod_upper in self.itens_estado:
                check_var = self.itens_estado[cod_upper]["check_var"]
                qtd_val = self.itens_estado[cod_upper]["qtd"]
            else:
                ja_selecionado = (cod_upper in self.componentes_iniciais_map)
                qtd_val = self.componentes_iniciais_map[cod_upper].quantidade if ja_selecionado else 1
                check_var = ctk.BooleanVar(value=ja_selecionado)

            # Checkbox com código
            chk = ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=check_var,
                width=24,
                command=self._ao_alterar_checkbox
            )
            chk.pack(side="left", padx=(10, 5), pady=8)

            # Badge do CO
            lbl_badge = ctk.CTkLabel(
                row_frame,
                text=cod,
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                fg_color=("#faeccf", "#3a2c14"),
                text_color=("#b35a00", "#f39c12"),
                corner_radius=4,
                width=80,
                height=24
            )
            lbl_badge.pack(side="left", padx=5)

            # Nome do Componente
            lbl_nome = ctk.CTkLabel(
                row_frame,
                text=nome,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            lbl_nome.pack(side="left", fill="x", expand=True, padx=8)

            if is_manual:
                lbl_tag = ctk.CTkLabel(
                    row_frame,
                    text="Manual",
                    font=ctk.CTkFont(size=10),
                    text_color="gray"
                )
                lbl_tag.pack(side="left", padx=5)

            # Controle de Quantidade
            lbl_qtd_txt = ctk.CTkLabel(
                row_frame,
                text="Qtd:",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            lbl_qtd_txt.pack(side="left", padx=(5, 2))

            entry_qtd = ctk.CTkEntry(
                row_frame,
                font=ctk.CTkFont(size=12),
                width=45,
                height=28,
                justify="center"
            )
            entry_qtd.insert(0, str(qtd_val))
            entry_qtd.pack(side="left", padx=(0, 10))
            entry_qtd.bind("<KeyRelease>", lambda e: self._atualizar_resumo())

            # Salva estado
            self.itens_estado[cod_upper] = {
                "codigo": cod,
                "nome": nome,
                "check_var": check_var,
                "entry_qtd": entry_qtd,
                "qtd": qtd_val
            }

        self._atualizar_resumo()

    def _ao_alterar_checkbox(self):
        self._atualizar_resumo()

    def _filtrar_exibicao(self):
        # Salva valores digitados nos entries de quantidade antes de re-renderizar
        for cod_u, info in self.itens_estado.items():
            if "entry_qtd" in info and info["entry_qtd"].winfo_exists():
                try:
                    val = int(info["entry_qtd"].get().strip())
                    if val > 0:
                        info["qtd"] = val
                except ValueError:
                    pass
        self._renderizar_itens()

    def _adicionar_co_manual(self):
        cod = self.entry_manual_cod.get().strip().upper()
        nome = self.entry_manual_nome.get().strip()
        qtd_txt = self.entry_manual_qtd.get().strip()

        if not cod:
            messagebox.showwarning("Código Obrigatório", "Digite o código do componente (ex: CO-0005).", parent=self)
            self.entry_manual_cod.focus()
            return

        val_cod, msg_cod = validar_codigo(cod, tipo="CO")
        if not val_cod:
            messagebox.showerror("Código Inválido", msg_cod, parent=self)
            self.entry_manual_cod.focus()
            return

        if not nome:
            nome = f"Componente {cod}"

        try:
            qtd = int(qtd_txt) if qtd_txt else 1
            if qtd <= 0:
                qtd = 1
        except ValueError:
            qtd = 1

        # Adiciona aos manuais e marca como selecionado
        novo_item = ComponenteItem(codigo=cod, nome=nome, quantidade=qtd)
        self.componentes_manuais.append(novo_item)
        self.componentes_iniciais_map[cod] = novo_item

        if cod in self.itens_estado:
            self.itens_estado[cod]["check_var"].set(True)
            self.itens_estado[cod]["qtd"] = qtd
        else:
            self.itens_estado[cod] = {
                "codigo": cod,
                "nome": nome,
                "check_var": ctk.BooleanVar(value=True),
                "qtd": qtd
            }

        # Limpa campos
        self.entry_manual_cod.delete(0, "end")
        self.entry_manual_nome.delete(0, "end")
        self.entry_manual_qtd.delete(0, "end")
        self.entry_manual_qtd.insert(0, "1")

        self._renderizar_itens()

    def _obter_selecionados(self) -> List[ComponenteItem]:
        selecionados: List[ComponenteItem] = []
        for cod_u, info in self.itens_estado.items():
            if info["check_var"].get():
                qtd = info.get("qtd", 1)
                if "entry_qtd" in info and info["entry_qtd"].winfo_exists():
                    try:
                        val = int(info["entry_qtd"].get().strip())
                        if val > 0:
                            qtd = val
                    except ValueError:
                        pass
                selecionados.append(
                    ComponenteItem(
                        codigo=info["codigo"],
                        nome=info["nome"],
                        quantidade=qtd
                    )
                )
        return selecionados

    def _atualizar_resumo(self):
        selecionados = self._obter_selecionados()
        total_tipos = len(selecionados)
        total_unidades = sum(s.quantidade for s in selecionados)

        texto = f"{total_tipos} componentes selecionados ({total_unidades} unidades no total)"
        if total_tipos > 0:
            amostra = ", ".join([f"{s.codigo} (x{s.quantidade})" for s in selecionados[:3]])
            if total_tipos > 3:
                amostra += f" e mais {total_tipos - 3}..."
            texto += f"\n• {amostra}"

        self.lbl_resumo_selecao.configure(
            text=texto,
            text_color=("#1f6aa5", "#64b5f6") if total_tipos > 0 else "gray"
        )

    def _confirmar_selecao(self):
        selecionados = self._obter_selecionados()
        self.on_confirm(selecionados)
        self.destroy()
