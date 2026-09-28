"""
Modelos de dados para o Controle CAD.
Representa peças, revisões, histórico e problemas encontrados em auditorias.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import datetime
import os


def obter_usuario_atual() -> str:
    """Retorna o nome do usuário ativo no Windows."""
    return os.environ.get("USERNAME") or os.environ.get("USER") or "Projetista"


@dataclass
class HistoricoEntrada:
    revisao: str
    data: str
    usuario: str
    motivo: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoricoEntrada":
        return cls(
            revisao=data.get("revisao", "A"),
            data=data.get("data", ""),
            usuario=data.get("usuario", "Projetista"),
            motivo=data.get("motivo", "")
        )


@dataclass
class ComponenteItem:
    codigo: str
    nome: str = ""
    quantidade: int = 1
    observacao: str = ""

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "quantidade": self.quantidade,
            "observacao": self.observacao,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComponenteItem":
        if isinstance(data, str):
            return cls(codigo=data)
        return cls(
            codigo=data.get("codigo", ""),
            nome=data.get("nome", ""),
            quantidade=int(data.get("quantidade", 1)),
            observacao=data.get("observacao", ""),
        )


LINHAS_PRODUTO = ["MedicalFix", "DentFix", "TraumaFix"]


@dataclass
class PecaInfo:
    codigo: str
    nome: str
    descricao: str = ""
    tipo: str = "Peça"  # "Peça", "Montagem" ou "CO"
    revisao_atual: str = "A"
    criado_por: str = field(default_factory=obter_usuario_atual)
    criado_em: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    )
    pasta_path: str = ""
    historico: List[HistoricoEntrada] = field(default_factory=list)
    componentes: List[ComponenteItem] = field(default_factory=list)
    kits: List[str] = field(default_factory=list)
    linha_produto: str = "MedicalFix"  # "MedicalFix", "DentFix" ou "TraumaFix"

    def to_dict(self) -> dict:
        dados = {
            "codigo": self.codigo,
            "nome": self.nome,
            "descricao": self.descricao,
            "tipo": self.tipo,
            "revisao_atual": self.revisao_atual,
            "criado_por": self.criado_por,
            "criado_em": self.criado_em,
            "historico": [h.to_dict() for h in self.historico],
            "linha_produto": self.linha_produto or "MedicalFix",
        }
        if self.componentes:
            dados["componentes"] = [c.to_dict() for c in self.componentes]
        if self.kits:
            dados["kits"] = self.kits
        return dados

    @classmethod
    def from_dict(cls, data: dict, pasta_path: str = "") -> "PecaInfo":
        historico_list = [
            HistoricoEntrada.from_dict(h) for h in data.get("historico", [])
        ]
        componentes_list = [
            ComponenteItem.from_dict(c) for c in data.get("componentes", [])
        ]
        kits_raw = data.get("kits", [])
        kits_list = [str(k).strip() for k in kits_raw if str(k).strip()]
        linha_produto = data.get("linha_produto") or data.get("linha") or "MedicalFix"
        return cls(
            codigo=data.get("codigo", ""),
            nome=data.get("nome", ""),
            descricao=data.get("descricao", ""),
            tipo=data.get("tipo", "Peça"),
            revisao_atual=data.get("revisao_atual", "A"),
            criado_por=data.get("criado_por", "Projetista"),
            criado_em=data.get("criado_em", ""),
            pasta_path=pasta_path,
            historico=historico_list,
            componentes=componentes_list,
            kits=kits_list,
            linha_produto=linha_produto,
        )


@dataclass
class ProblemaAuditoria:
    categoria: str  # "PASTA_FORA_PADRAO", "ARQUIVO_FORA_PADRAO", "INCONSISTENCIA", "ESTRUTURA_INCOMPLETA", "DUPLICIDADE"
    caminho: str
    descricao: str
    sugestao: Optional[str] = None
    corrigivel: bool = False
    novo_caminho: Optional[str] = None
