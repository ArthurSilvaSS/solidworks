"""
Serviço de Detecção de Duplicidade do Controle CAD.
Verifica:
1. Código já cadastrado (bloqueio obrigatório)
2. Peças com nomes semelhantes (alerta consultivo com SequenceMatcher)
3. Duplicidade binária por hash SHA-256
"""

import os
import hashlib
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Dict
from core.models import PecaInfo
from services.storage_service import StorageService
from core.logger import registrar_log


def calcular_hash_arquivo(caminho_arquivo: str, tamanho_bloco: int = 65536) -> Optional[str]:
    """Calcula o hash SHA-256 de um arquivo."""
    if not os.path.exists(caminho_arquivo) or not os.path.isfile(caminho_arquivo):
        return None
    
    sha = hashlib.sha256()
    try:
        with open(caminho_arquivo, "rb") as f:
            while True:
                dados = f.read(tamanho_bloco)
                if not dados:
                    break
                sha.update(dados)
        return sha.hexdigest()
    except Exception as e:
        print(f"Erro ao calcular hash de {caminho_arquivo}: {e}")
        return None


class DuplicateService:
    def __init__(self, storage_service: StorageService):
        self.storage = storage_service

    def verificar_codigo_existente(self, codigo: str) -> Optional[PecaInfo]:
        """
        Verifica se já existe alguma peça com o código especificado.
        Se existir, retorna a PecaInfo correspondente para bloqueio.
        """
        codigo_limpo = codigo.strip().upper()
        todas = self.storage.listar_todas_pecas()
        for p in todas:
            if p.codigo.upper() == codigo_limpo:
                return p
        return None

    def buscar_nomes_semelhantes(
        self, nome_procurado: str, limiar_similaridade: float = 0.55
    ) -> List[Tuple[PecaInfo, float]]:
        """
        Busca peças existentes com nomes semelhantes para evitar duplicações conceituais.
        Retorna lista de tuplas (PecaInfo, score_similaridade) ordenadas por relevância.
        """
        nome_proc_lower = nome_procurado.strip().lower()
        palavras_busca = set(nome_proc_lower.split())
        resultados: List[Tuple[PecaInfo, float]] = []

        todas = self.storage.listar_todas_pecas()
        for p in todas:
            nome_existente = p.nome.strip().lower()
            
            # 1. Checagem de SequenceMatcher direta
            score_direto = SequenceMatcher(None, nome_proc_lower, nome_existente).ratio()
            
            # 2. Checagem de sobreposição de termos
            palavras_existentes = set(nome_existente.split())
            intersecao = palavras_busca.intersection(palavras_existentes)
            score_palavras = len(intersecao) / max(len(palavras_busca), 1) if intersecao else 0.0
            
            # Score final ponderado
            score_final = max(score_direto, (score_direto * 0.5 + score_palavras * 0.5))
            
            if score_final >= limiar_similaridade:
                resultados.append((p, round(score_final, 2)))

        resultados.sort(key=lambda x: x[1], reverse=True)
        return resultados

    def verificar_duplicidade_hash_cad(self, caminho_arquivo_novo: str) -> List[Tuple[PecaInfo, str]]:
        """
        Varre todos os arquivos CAD existentes na raiz procurando arquivos idênticos (mesmo SHA-256).
        Retorna lista de (PecaInfo, caminho_arquivo_duplicado).
        """
        hash_novo = calcular_hash_arquivo(caminho_arquivo_novo)
        if not hash_novo:
            return []

        duplicados: List[Tuple[PecaInfo, str]] = []
        todas = self.storage.listar_todas_pecas()
        
        for p in todas:
            caminho_cad = self.storage.obter_caminho_cad(p)
            if caminho_cad and os.path.abspath(caminho_cad) != os.path.abspath(caminho_arquivo_novo):
                hash_existente = calcular_hash_arquivo(caminho_cad)
                if hash_existente and hash_existente == hash_novo:
                    duplicados.append((p, caminho_cad))
                    registrar_log(
                        "POSSÍVEL DUPLICIDADE DE CONTEÚDO",
                        {
                            "Arquivo 1": caminho_arquivo_novo,
                            "Arquivo 2": caminho_cad,
                            "Hash": hash_novo,
                            "Peça": f"{p.codigo} - {p.nome}"
                        },
                        nivel="WARNING"
                    )

        return duplicados
