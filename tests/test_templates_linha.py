"""
Testes unitários para a seleção e resolução automática de templates de folha 2D
por grupo / linha de produto (MedicalFix, DentFix, TraumaFix).
"""

import os
import unittest
import tempfile
import shutil
from cad.solidworks_client import SolidWorksClient
from core.config import carregar_config, salvar_config, CONFIG_PADRAO


class TestTemplatesLinha(unittest.TestCase):
    def setUp(self):
        self.sw_client = SolidWorksClient(modo_simulacao=True)
        self.temp_dir = tempfile.mkdtemp(prefix="controle_cad_tmpl_test_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolucao_templates_linhas_conhecidas(self):
        """Valida que cada grupo resolve para o seu respectivo arquivo .drwdot."""
        tmpl_med = self.sw_client.obter_template_desenho_por_linha("MedicalFix")
        tmpl_dent = self.sw_client.obter_template_desenho_por_linha("DentFix")
        tmpl_trauma = self.sw_client.obter_template_desenho_por_linha("TraumaFix")

        self.assertTrue(bool(tmpl_med), "Template MedicalFix não foi localizado")
        self.assertTrue(bool(tmpl_dent), "Template DentFix não foi localizado")
        self.assertTrue(bool(tmpl_trauma), "Template TraumaFix não foi localizado")

        self.assertIn("MEDICALFIX", os.path.basename(tmpl_med).upper())
        self.assertIn("DENTFIX", os.path.basename(tmpl_dent).upper())
        self.assertIn("TRAUMAFIX", os.path.basename(tmpl_trauma).upper())

    def test_criar_desenho_simulado_com_template_linha(self):
        """Verifica se a criação de desenho grava o template correto da linha."""
        caminho_des = os.path.join(self.temp_dir, "DESENHO", "100.001.SLDDRW")
        ok, msg = self.sw_client.criar_novo_desenho_cad(
            codigo="100.001",
            nome="Implante Teste",
            tipo="Peça",
            caminho_salvar_desenho=caminho_des,
            linha_produto="DentFix"
        )
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(caminho_des))

        with open(caminho_des, "r", encoding="utf-8") as f:
            conteudo = f.read()

        self.assertIn("LINHA=DentFix", conteudo)
        self.assertIn("DENTFIX.DRWDOT", conteudo.upper())

    def test_criar_montagem_com_componentes(self):
        """Valida que a criação de montagem lida corretamente com objetos ComponenteItem sem erros."""
        from core.models import ComponenteItem
        caminho_asm = os.path.join(self.temp_dir, "CAD", "200.001.SLDASM")
        componentes = [
            ComponenteItem(codigo="CO-1001", quantidade=2),
            ComponenteItem(codigo="CO-1002", quantidade=4)
        ]
        ok, msg = self.sw_client.criar_novo_documento_cad(
            codigo="200.001",
            nome="Montagem Cabeçote",
            tipo="Montagem",
            caminho_salvar=caminho_asm,
            componentes=componentes
        )
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(caminho_asm))

        with open(caminho_asm, "r", encoding="utf-8") as f:
            conteudo = f.read()

        self.assertIn("TIPO=Montagem", conteudo)
        self.assertIn("COMPONENTES_CO=CO-1001 (x2); CO-1002 (x4)", conteudo)


if __name__ == "__main__":
    unittest.main()
