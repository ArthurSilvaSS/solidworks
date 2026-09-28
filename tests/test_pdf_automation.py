"""
Testes unitários e de integração para o serviço de automação de PDF.
Verifica a detecção inteligente de projetos com CAD e Desenho 2D,
bem como a geração autônoma e atualização de PDFs.
"""

import os
import time
import shutil
import tempfile
import unittest
import threading

from core.models import PecaInfo
from services.storage_service import StorageService
from services.pdf_automation_service import PdfAutomationService
from cad.solidworks_client import SolidWorksClient


class TestPdfAutomation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="controle_cad_pdf_test_")
        self.storage = StorageService(self.temp_dir)
        self.sw_client = SolidWorksClient(modo_simulacao=True)
        self.config = {
            "pasta_raiz": self.temp_dir,
            "criar_pdf": True,
            "monitorar_pasta": True,
            "modo_simulacao_sw": True
        }
        self.pdf_service = PdfAutomationService(self.storage, self.sw_client, self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verificacao_status_cad_desenho_pdf(self):
        """Testa as funções de verificação de presença de CAD, Desenho 2D e PDF."""
        peca = PecaInfo(codigo="250.010", nome="Base do Suporte")
        sucesso, pasta = self.storage.criar_estrutura_peca(peca)
        self.assertTrue(sucesso)

        # 1. Nenhum arquivo ainda
        self.assertFalse(self.storage.peca_tem_cad(peca))
        self.assertFalse(self.storage.peca_tem_desenho(peca))
        self.assertFalse(self.storage.peca_tem_pdf(peca))
        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        self.assertFalse(precisa)
        self.assertIn("modelo 3D", motivo)

        # 2. Cria arquivo CAD (.SLDPRT)
        caminho_cad = os.path.join(pasta, "CAD", "250.010.SLDPRT")
        with open(caminho_cad, "w") as f:
            f.write("CAD_DATA")

        self.assertTrue(self.storage.peca_tem_cad(peca))
        self.assertFalse(self.storage.peca_tem_desenho(peca))
        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        self.assertFalse(precisa)
        self.assertIn("desenho 2D", motivo)

        # 3. Cria arquivo de Desenho 2D (.SLDDRW)
        caminho_des = os.path.join(pasta, "DESENHO", "250.010.SLDDRW")
        with open(caminho_des, "w") as f:
            f.write("DRAWING_DATA")

        self.assertTrue(self.storage.peca_tem_cad(peca))
        self.assertTrue(self.storage.peca_tem_desenho(peca))
        self.assertFalse(self.storage.peca_tem_pdf(peca))

        # Agora possui CAD e Desenho, mas falta o PDF: DEVE PRECISAR GERAR SOZINHO!
        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        self.assertTrue(precisa)
        self.assertIn("ainda não foi gerado", motivo)

        # 4. Simula geração do PDF
        caminho_pdf = os.path.join(pasta, "PDF", "250.010.pdf")
        with open(caminho_pdf, "w") as f:
            f.write("PDF_DATA")

        self.assertTrue(self.storage.peca_tem_pdf(peca))
        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        self.assertFalse(precisa)
        self.assertIn("já está atualizado", motivo)

        # 5. Modifica o arquivo de desenho 2D com data mais recente
        time.sleep(0.05)
        with open(caminho_des, "a") as f:
            f.write("\nALTERACAO_DESENHO")

        precisa, motivo = self.storage.peca_precisa_gerar_pdf(peca)
        self.assertTrue(precisa)
        self.assertIn("alterado após o último PDF", motivo)

    def test_geracao_automatica_de_pdf(self):
        """Testa o disparo e criação automática do PDF pelo serviço de automação."""
        peca = PecaInfo(codigo="250.011", nome="Eixo Redutor")
        _, pasta = self.storage.criar_estrutura_peca(peca)

        # Cria CAD e Desenho
        caminho_cad = os.path.join(pasta, "CAD", "250.011.SLDPRT")
        with open(caminho_cad, "w") as f:
            f.write("CAD")
        caminho_des = os.path.join(pasta, "DESENHO", "250.011.SLDDRW")
        with open(caminho_des, "w") as f:
            f.write("DESENHO")

        # Verifica pendências
        pendentes = self.pdf_service.obter_pecas_com_pdf_pendente()
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0][0].codigo, "250.011")

        # Executa geração automática
        ok, msg = self.pdf_service.gerar_pdf_peca(peca)
        self.assertTrue(ok)

        # Confirma que o PDF foi criado na pasta correta
        caminho_pdf_gerado = os.path.join(pasta, "PDF", "250.011.pdf")
        self.assertTrue(os.path.exists(caminho_pdf_gerado))
        self.assertTrue(self.storage.peca_tem_pdf(peca))

        # Confirma que agora não há mais pendências
        pendentes_apos = self.pdf_service.obter_pecas_com_pdf_pendente()
        self.assertEqual(len(pendentes_apos), 0)

    def test_geracao_assincrona_em_background(self):
        """Testa se a geração em background roda em thread separada e notifica callback."""
        peca = PecaInfo(codigo="250.012", nome="Flange de Saída")
        _, pasta = self.storage.criar_estrutura_peca(peca)

        with open(os.path.join(pasta, "CAD", "250.012.SLDPRT"), "w") as f:
            f.write("CAD")
        with open(os.path.join(pasta, "DESENHO", "250.012.SLDDRW"), "w") as f:
            f.write("DESENHO")

        evento_concluido = threading.Event()
        resultado = []

        def _on_sucesso(p):
            resultado.append(p.codigo)
            evento_concluido.set()

        self.pdf_service.gerar_pdf_async(peca, on_success=_on_sucesso)

        # Aguarda thread concluir
        sucesso = evento_concluido.wait(timeout=3.0)
        self.assertTrue(sucesso)
        self.assertIn("250.012", resultado)
        self.assertTrue(self.storage.peca_tem_pdf(peca))


if __name__ == "__main__":
    unittest.main()
