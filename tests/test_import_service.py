"""
Testes automatizados para os recursos de Importação de Peças Prontas (3D e 2D).
"""

import os
import shutil
import tempfile
import unittest
from services.storage_service import StorageService
from core.models import PecaInfo, ComponenteItem


class TestImportacaoPecasProntas(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="controle_cad_import_test_")
        self.storage = StorageService(self.temp_dir)
        self.origem_dir = tempfile.mkdtemp(prefix="origem_pecas_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.origem_dir, ignore_errors=True)

    def test_extrair_dados_de_arquivo(self):
        # 1. Padrão estrito 000.000 - Nome
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("250.001 - Suporte Motor.SLDPRT")
        self.assertEqual(cod, "250.001")
        self.assertEqual(nome, "Suporte Motor")
        self.assertEqual(tipo, "Peça")

        # 2. Montagem .SLDASM
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("100.005 - Conjunto Redutor.SLDASM")
        self.assertEqual(cod, "100.005")
        self.assertEqual(nome, "Conjunto Redutor")
        self.assertEqual(tipo, "Montagem")

        # 3. Componente CO-0000
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("CO-0012 - Parafuso Sextavado M6.SLDPRT")
        self.assertEqual(cod, "CO-0012")
        self.assertEqual(nome, "Parafuso Sextavado M6")
        self.assertEqual(tipo, "CO")

        # 4. Formato corrigível 6 dígitos juntos
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("300001 - Eixo Principal.SLDPRT")
        self.assertEqual(cod, "300.001")
        self.assertEqual(nome, "Eixo Principal")

        # 5. Formato corrigível CO sem hífen
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("CO0003 - Retentor.SLDPRT")
        self.assertEqual(cod, "CO-0003")
        self.assertEqual(nome, "Retentor")
        self.assertEqual(tipo, "CO")

        # 6. Arquivo sem código (apenas descrição)
        cod, nome, tipo = StorageService.extrair_dados_de_arquivo("Flange de Acoplamento.SLDPRT")
        self.assertIsNone(cod)
        self.assertEqual(nome, "Flange de Acoplamento")
        self.assertEqual(tipo, "Peça")

    def test_importar_peca_existente_sucesso(self):
        # Cria arquivos fictícios de 3D, 2D e PDF na pasta de origem
        arq_3d = os.path.join(self.origem_dir, "Modelo_Teste.SLDPRT")
        arq_2d = os.path.join(self.origem_dir, "Modelo_Teste.SLDDRW")
        arq_pdf = os.path.join(self.origem_dir, "Modelo_Teste.pdf")

        with open(arq_3d, "w") as f:
            f.write("DADOS_3D_SOLIDWORKS")
        with open(arq_2d, "w") as f:
            f.write("DADOS_2D_DESENHO")
        with open(arq_pdf, "w") as f:
            f.write("DADOS_PDF")

        # Executa importação
        sucesso, peca, msg = self.storage.importar_peca_existente(
            caminho_3d=arq_3d,
            caminho_2d=arq_2d,
            caminho_pdf=arq_pdf,
            codigo="250.001",
            nome="Suporte Teste",
            tipo="Peça",
            descricao="Suporte em aço inox",
            revisao="B",
            kits=["Kit Coluna", "Kit Teste"],
            copiar=True
        )

        self.assertTrue(sucesso, f"Falha na importação: {msg}")
        self.assertIsNotNone(peca)
        self.assertEqual(peca.codigo, "250.001")
        self.assertEqual(peca.nome, "Suporte Teste")
        self.assertEqual(peca.revisao_atual, "B")
        self.assertIn("Kit Coluna", peca.kits)

        # Verifica pastas e arquivos padronizados criados
        pasta_peca = os.path.join(self.temp_dir, "250.001 - Suporte Teste")
        self.assertTrue(os.path.isdir(pasta_peca))
        self.assertTrue(os.path.isfile(os.path.join(pasta_peca, "CAD", "250.001.SLDPRT")))
        self.assertTrue(os.path.isfile(os.path.join(pasta_peca, "DESENHO", "250.001.SLDDRW")))
        self.assertTrue(os.path.isfile(os.path.join(pasta_peca, "PDF", "250.001.pdf")))
        self.assertTrue(os.path.isdir(os.path.join(pasta_peca, "HISTORICO")))
        self.assertTrue(os.path.isfile(os.path.join(pasta_peca, "controle.json")))

        # Os arquivos originais devem continuar intactos (pois copiar=True)
        self.assertTrue(os.path.exists(arq_3d))
        self.assertTrue(os.path.exists(arq_2d))

        # Tentar importar de novo com mesmo código deve falhar
        ok_dup, _, msg_dup = self.storage.importar_peca_existente(
            caminho_3d=arq_3d,
            codigo="250.001",
            nome="Outro Suporte"
        )
        self.assertFalse(ok_dup)
        self.assertIn("já está cadastrado", msg_dup)

    def test_importar_componente_co(self):
        arq_3d = os.path.join(self.origem_dir, "Rolamento.SLDPRT")
        with open(arq_3d, "w") as f:
            f.write("DADOS_CO")

        sucesso, peca, msg = self.storage.importar_peca_existente(
            caminho_3d=arq_3d,
            codigo="co-0001",
            nome="Rolamento 608",
            tipo="CO"
        )

        self.assertTrue(sucesso)
        self.assertEqual(peca.codigo, "CO-0001")
        self.assertEqual(peca.tipo, "CO")
        pasta_co = os.path.join(self.temp_dir, "CO-0001 - Rolamento 608")
        self.assertTrue(os.path.isdir(pasta_co))
        self.assertTrue(os.path.isfile(os.path.join(pasta_co, "CAD", "CO-0001.SLDPRT")))

    def test_escanear_pasta_externa(self):
        # Cria estrutura simulada na pasta de origem com pares 3D+2D
        arq1_3d = os.path.join(self.origem_dir, "250.010 - Base.SLDPRT")
        arq1_2d = os.path.join(self.origem_dir, "250.010 - Base.SLDDRW")
        arq2_3d = os.path.join(self.origem_dir, "100.001 - Conjunto.SLDASM")
        arq3_3d = os.path.join(self.origem_dir, "SemCodigo.SLDPRT")

        for a in [arq1_3d, arq1_2d, arq2_3d, arq3_3d]:
            with open(a, "w") as f:
                f.write("TESTE")

        itens = self.storage.escanear_pasta_externa(self.origem_dir)
        self.assertEqual(len(itens), 3)

        item_base = next(i for i in itens if i["nome"] == "Base")
        self.assertEqual(item_base["codigo"], "250.010")
        self.assertTrue(item_base["tem_3d"])
        self.assertTrue(item_base["tem_2d"])

        item_conj = next(i for i in itens if i["nome"] == "Conjunto")
        self.assertEqual(item_conj["tipo"], "Montagem")
        self.assertTrue(item_conj["tem_3d"])
        self.assertFalse(item_conj["tem_2d"])


if __name__ == "__main__":
    unittest.main()
