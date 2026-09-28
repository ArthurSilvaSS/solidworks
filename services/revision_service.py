"""
Serviço de Controle de Revisões do Controle CAD.
Responsável por:
1. Calcular a próxima letra de revisão (A -> B -> C...)
2. Arquivar o estado atual em HISTORICO\\REV_<atual>
3. Manter os arquivos de trabalho ativos sem sufixo no nome
4. Atualizar o controle.json e registrar em controle_cad.log
"""

import os
import shutil
from datetime import datetime
from typing import Tuple, Optional
from core.models import PecaInfo, HistoricoEntrada, obter_usuario_atual
from core.validator import proxima_revisao
from core.logger import registrar_log
from services.storage_service import StorageService


class RevisionService:
    def __init__(self, storage_service: StorageService):
        self.storage = storage_service

    def criar_nova_revisao(
        self,
        peca: PecaInfo,
        motivo: str,
        usuario: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Executa o processo de criação de uma nova revisão:
        1. Copia arquivos atuais (CAD, DESENHO, PDF) para HISTORICO\\REV_<rev_atual>
        2. Atualiza revisao_atual no objeto e no controle.json
        3. Mantém os nomes dos arquivos de trabalho inalterados (ex: 250.001.SLDPRT)
        
        Retorna (sucesso, nova_revisao, mensagem).
        """
        if not motivo or not motivo.strip():
            return False, peca.revisao_atual, "O motivo da revisão é obrigatório."

        rev_anterior = peca.revisao_atual or "A"
        proxima_rev = proxima_revisao(rev_anterior)
        autor = usuario or obter_usuario_atual()
        data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        # 1. Pasta de histórico para a revisão que está sendo arquivada
        pasta_historico = os.path.join(peca.pasta_path, "HISTORICO", f"REV_{rev_anterior}")
        try:
            os.makedirs(pasta_historico, exist_ok=True)
        except Exception as e:
            return False, rev_anterior, f"Não foi possível criar a pasta de histórico: {e}"

        # 2. Copia arquivos atuais para a pasta de histórico
        arquivos_copiados = []
        caminho_cad = self.storage.obter_caminho_cad(peca)
        if caminho_cad and os.path.exists(caminho_cad):
            destino_cad = os.path.join(pasta_historico, os.path.basename(caminho_cad))
            shutil.copy2(caminho_cad, destino_cad)
            arquivos_copiados.append(os.path.basename(caminho_cad))

        caminho_desenho = self.storage.obter_caminho_desenho(peca)
        if caminho_desenho and os.path.exists(caminho_desenho):
            destino_des = os.path.join(pasta_historico, os.path.basename(caminho_desenho))
            shutil.copy2(caminho_desenho, destino_des)
            arquivos_copiados.append(os.path.basename(caminho_desenho))

        caminho_pdf = self.storage.obter_caminho_pdf(peca)
        if caminho_pdf and os.path.exists(caminho_pdf):
            destino_pdf = os.path.join(pasta_historico, os.path.basename(caminho_pdf))
            shutil.copy2(caminho_pdf, destino_pdf)
            arquivos_copiados.append(os.path.basename(caminho_pdf))

        # 3. Atualiza os dados da peça
        peca.revisao_atual = proxima_rev
        nova_entrada = HistoricoEntrada(
            revisao=proxima_rev,
            data=data_agora,
            usuario=autor,
            motivo=motivo.strip()
        )
        peca.historico.append(nova_entrada)

        # 4. Salva o controle.json atualizado
        sucesso_salvar = self.storage.salvar_controle_json(peca)
        if not sucesso_salvar:
            return False, rev_anterior, "Erro ao atualizar controle.json."

        # 5. Registra no log de auditoria
        registrar_log(
            "REVISAO CRIADA",
            {
                "Código": peca.codigo,
                "Nome": peca.nome,
                "Transição": f"{rev_anterior} -> {proxima_rev}",
                "Motivo": motivo.strip(),
                "Usuário": autor,
                "Arquivos Arquivados": ", ".join(arquivos_copiados) if arquivos_copiados else "Nenhum arquivo físico"
            }
        )

        return True, proxima_rev, f"Revisão avançada de {rev_anterior} para {proxima_rev} com sucesso."
