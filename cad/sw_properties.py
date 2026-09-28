"""
Gerenciamento de Custom Properties (Propriedades Personalizadas) no SolidWorks.
Lê e grava propriedades como CODIGO, DESCRICAO, REVISAO e TIPO.
"""

from typing import Dict, Optional
from core.logger import registrar_log

# Tipos de propriedades personalizadas no SolidWorks (swCustomInfoType_e)
SW_CUSTOM_INFO_TEXT = 30


class SWPropertyManager:
    @staticmethod
    def definir_propriedade(model_doc, nome: str, valor: str) -> bool:
        """
        Define ou atualiza uma Custom Property no documento ativo do SolidWorks.
        Usa o CustomPropertyManager moderno da extensão do ModelDoc2.
        """
        if not model_doc:
            return False
        
        try:
            # Acessa o gerenciador de propriedades da configuração geral (vazio = documento/global)
            ext = getattr(model_doc, "Extension", None)
            if not ext:
                return False
                
            cust_prop_mgr = ext.CustomPropertyManager("")
            if not cust_prop_mgr:
                return False

            # Add3: (PropertyName, PropertyType, Value, OverwriteFlag)
            # Retorna 1 (swCustomInfoAddResult_AddedOrChanged) ou 0 se já existe
            # 1 = swCustomInfoAddResult_AddedOrChanged
            # 2 = swCustomInfoAddResult_GenericError
            res = cust_prop_mgr.Add3(nome, SW_CUSTOM_INFO_TEXT, str(valor), 1)
            
            # Se Add3 não alterou, força com Set2
            if res != 1:
                cust_prop_mgr.Set2(nome, str(valor))
                
            return True
        except Exception as e:
            registrar_log(
                "ERRO GRAVAR PROPRIEDADE SOLIDWORKS",
                {"Propriedade": nome, "Valor": valor, "Erro": str(e)},
                nivel="WARNING"
            )
            return False

    @staticmethod
    def ler_propriedade(model_doc, nome: str) -> Optional[str]:
        """Lê o valor de uma Custom Property do documento do SolidWorks."""
        if not model_doc:
            return None
            
        try:
            ext = getattr(model_doc, "Extension", None)
            if not ext:
                return None
                
            cust_prop_mgr = ext.CustomPropertyManager("")
            if not cust_prop_mgr:
                return None

            # Get6(FieldName, UseCached, ValOut, ResolvedValOut, WasResolved, LinkToProperty)
            # Em python win32com, métodos com parâmetros OUT retornam tupla
            res = cust_prop_mgr.Get6(nome, False, "", "", False, False)
            if isinstance(res, (tuple, list)) and len(res) >= 4:
                # O valor resolvido geralmente está no índice 3 ou 2
                valor_resolvido = res[3] or res[2]
                return str(valor_resolvido)
            
            # Fallback para CustomInfo2 legado se Get6 não retornar tupla esperada
            try:
                val_legado = model_doc.CustomInfo2("", nome)
                if val_legado:
                    return str(val_legado)
            except Exception:
                pass

            return None
        except Exception as e:
            registrar_log(
                "ERRO LER PROPRIEDADE SOLIDWORKS",
                {"Propriedade": nome, "Erro": str(e)},
                nivel="WARNING"
            )
            return None

    @classmethod
    def gravar_propriedades_padrao(
        cls,
        model_doc,
        codigo: str,
        descricao: str,
        revisao: str,
        tipo: str
    ) -> bool:
        """Grava as 4 propriedades padronizadas do Controle CAD."""
        sucesso = True
        sucesso &= cls.definir_propriedade(model_doc, "CODIGO", codigo)
        sucesso &= cls.definir_propriedade(model_doc, "DESCRICAO", descricao)
        sucesso &= cls.definir_propriedade(model_doc, "REVISAO", revisao)
        sucesso &= cls.definir_propriedade(model_doc, "TIPO", tipo)
        return sucesso

    @classmethod
    def ler_propriedades_padrao(cls, model_doc) -> Dict[str, Optional[str]]:
        """Lê as 4 propriedades padronizadas do documento."""
        return {
            "CODIGO": cls.ler_propriedade(model_doc, "CODIGO"),
            "DESCRICAO": cls.ler_propriedade(model_doc, "DESCRICAO"),
            "REVISAO": cls.ler_propriedade(model_doc, "REVISAO"),
            "TIPO": cls.ler_propriedade(model_doc, "TIPO"),
        }
