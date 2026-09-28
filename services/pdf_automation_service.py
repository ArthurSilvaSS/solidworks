"""
Serviço de Automação de PDF do Controle CAD.
Detecta automaticamente projetos que já possuem o modelo CAD (.SLDPRT/.SLDASM)
e a folha de desenho 2D (.SLDDRW), gerando e sincronizando o arquivo PDF
correspondente na pasta PDF de forma autônoma e sem necessidade de ação manual.
"""

import os
import threading
from typing import List, Tuple, Dict, Any, Optional, Callable, Set

from core.models import PecaInfo
from core.logger import registrar_log
from services.storage_service import StorageService
from cad.solidworks_client import SolidWorksClient


class PdfAutomationService:
    def __init__(
        self,
        storage_service: StorageService,
        sw_client: SolidWorksClient,
        config: Dict[str, Any]
    ):
        self.storage = storage_service
        self.sw_client = sw_client
        self.config = config
        self._em_processamento: Set[str] = set()
        self._lock = threading.Lock()

    def esta_processando(self, codigo: str) -> bool:
        """Indica se um desenho está sendo exportado para PDF no momento."""
        with self._lock:
            return codigo in self._em_processamento

    def obter_pecas_com_pdf_pendente(self) -> List[Tuple[PecaInfo, str]]:
        """
        Varre todos os projetos e retorna a lista de peças que já possuem CAD e Desenho 2D,
        mas cujo PDF ainda não foi gerado ou está desatualizado.
        """
        pendentes: List[Tuple[PecaInfo, str]] = []
        todas = self.storage.listar_todas_pecas()

        for peca in todas:
            precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
            if precisa:
                pendentes.append((peca, motivo))

        return pendentes

    def gerar_pdf_peca(self, peca: PecaInfo) -> Tuple[bool, str]:
        """
        Gera o PDF de forma síncrona a partir do desenho técnico 2D (.SLDDRW).
        """
        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        if not precisa and not os.path.exists(os.path.join(peca.pasta_path, "PDF", f"{peca.codigo}.pdf")):
            return False, motivo

        caminho_des = self.storage.obter_caminho_desenho(peca)
        if not caminho_des or not os.path.exists(caminho_des):
            return False, f"Desenho 2D não encontrado para {peca.codigo}."

        pasta_pdf = os.path.join(peca.pasta_path, "PDF")
        os.makedirs(pasta_pdf, exist_ok=True)
        caminho_pdf_destino = os.path.join(pasta_pdf, f"{peca.codigo}.pdf")

        with self._lock:
            self._em_processamento.add(peca.codigo)

        try:
            ok, msg = self.sw_client.gerar_pdf_de_desenho(caminho_des, caminho_pdf_destino)
            if ok:
                registrar_log(
                    "PDF AUTOMÁTICO GERADO",
                    {
                        "Código": peca.codigo,
                        "Nome": peca.nome,
                        "Desenho": caminho_des,
                        "PDF": caminho_pdf_destino,
                        "Motivo": motivo
                    },
                    nivel="INFO"
                )
            return ok, msg
        finally:
            with self._lock:
                self._em_processamento.discard(peca.codigo)

    def gerar_pdf_async(
        self,
        peca: PecaInfo,
        on_success: Optional[Callable[[PecaInfo], None]] = None,
        on_error: Optional[Callable[[PecaInfo, str], None]] = None
    ):
        """
        Executa a geração do PDF em uma thread secundária para não travar a interface gráfica.
        Inicializa o subsistema COM no Windows para compatibilidade segura com o SolidWorks.
        """
        if self.esta_processando(peca.codigo):
            return

        def _worker():
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

            try:
                sucesso, msg = self.gerar_pdf_peca(peca)
                if sucesso:
                    if on_success:
                        on_success(peca)
                else:
                    if on_error:
                        on_error(peca, msg)
            except Exception as e:
                if on_error:
                    on_error(peca, str(e))
            finally:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        t = threading.Thread(target=_worker, daemon=True, name=f"AutoPDF_{peca.codigo}")
        t.start()

    def processar_pendencias_em_background(
        self,
        on_peca_concluida: Optional[Callable[[PecaInfo], None]] = None,
        on_tudo_concluido: Optional[Callable[[int, int], None]] = None
    ):
        """
        Varre todos os projetos com PDF pendente e os processa sequencialmente em background.
        """
        pendentes = self.obter_pecas_com_pdf_pendente()
        if not pendentes:
            if on_tudo_concluido:
                on_tudo_concluido(0, 0)
            return

        def _batch_worker():
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

            sucessos = 0
            total = len(pendentes)

            try:
                for peca, _ in pendentes:
                    ok, _ = self.gerar_pdf_peca(peca)
                    if ok:
                        sucessos += 1
                        if on_peca_concluida:
                            on_peca_concluida(peca)
            finally:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

                if on_tudo_concluido:
                    on_tudo_concluido(sucessos, total)

        t = threading.Thread(target=_batch_worker, daemon=True, name="AutoPDF_Batch")
        t.start()
