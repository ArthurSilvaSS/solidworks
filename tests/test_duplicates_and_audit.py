"""
Testes de Detecção de Duplicidade e Auditoria de Projetos.
"""

import os
import shutil
import tempfile
import unittest
from core.models import PecaInfo
from services.storage_service import StorageService
from services.duplicate_service import DuplicateService, calcular_hash_arquivo
from services.audit_service import AuditService


class TestDuplicatesAndAudit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="controle_cad_dup_test_")
        self.storage = StorageService(self.temp_dir)
        self.duplicate = DuplicateService(self.storage)
        self.audit = AuditService(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verificar_codigo_existente(self):
        peca = PecaInfo(codigo="250.001", nome="Parafuso")
        self.storage.criar_estrutura_peca(peca)

        # Busca código existente
        encontrado = self.duplicate.verificar_codigo_existente("250.001")
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado.codigo, "250.001")

        # Código não existente
        inexistente = self.duplicate.verificar_codigo_existente("250.999")
        self.assertIsNone(inexistente)

    def test_buscar_nomes_semelhantes(self):
        pecas = [
            PecaInfo(codigo="250.001", nome="Parafuso M8"),
            PecaInfo(codigo="250.015", nome="Parafuso M8 x 20"),
            PecaInfo(codigo="250.016", nome="Parafuso M8 x 40"),
            PecaInfo(codigo="300.001", nome="Eixo Principal"),
        ]
        for p in pecas:
            self.storage.criar_estrutura_peca(p)

        # Procura por "Parafuso M8 x 35"
        semelhantes = self.duplicate.buscar_nomes_semelhantes("Parafuso M8 x 35", limiar_similaridade=0.5)
        self.assertTrue(len(semelhantes) >= 2)
        codigos_encontrados = [p.codigo for p, score in semelhantes]
        self.assertIn("250.015", codigos_encontrados)
        self.assertIn("250.016", codigos_encontrados)
        self.assertNotIn("300.001", codigos_encontrados)

    def test_duplicidade_hash_binario(self):
        peca1 = PecaInfo(codigo="250.001", nome="Parafuso A")
        self.storage.criar_estrutura_peca(peca1)
        cad1 = os.path.join(peca1.pasta_path, "CAD", "250.001.SLDPRT")
        with open(cad1, "wb") as f:
            f.write(b"CONTEUDO_BINARIO_EXATO_SOLIDWORKS_123")

        # Arquivo novo em outro local com mesmo conteúdo
        temp_novo = os.path.join(self.temp_dir, "temporario.SLDPRT")
        with open(temp_novo, "wb") as f:
            f.write(b"CONTEUDO_BINARIO_EXATO_SOLIDWORKS_123")

        dups = self.duplicate.verificar_duplicidade_hash_cad(temp_novo)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0][0].codigo, "250.001")

    def test_auditoria_projetos_e_correcao(self):
        # 1. Cria pasta fora do padrão que pode ser corrigida (123456 - Parafuso)
        pasta_corrigivel = os.path.join(self.temp_dir, "123456 - Parafuso")
        os.makedirs(pasta_corrigivel)

        # 2. Cria pasta válida mas com arquivo fora do padrão (_FINAL)
        peca_valida = PecaInfo(codigo="250.001", nome="Suporte")
        self.storage.criar_estrutura_peca(peca_valida)
        arq_errado = os.path.join(peca_valida.pasta_path, "CAD", "250.001_FINAL.SLDPRT")
        with open(arq_errado, "w") as f:
            f.write("teste")

        problemas = self.audit.executar_auditoria_completa()
        self.assertTrue(len(problemas) >= 2)

        # Encontra o problema da pasta corrigível
        prob_pasta = next((p for p in problemas if p.categoria == "PASTA_FORA_PADRAO"), None)
        self.assertIsNotNone(prob_pasta)
        self.assertTrue(prob_pasta.corrigivel)

        # Aplica correção automática
        ok_corrigir, msg = self.audit.corrigir_pasta_automatica(prob_pasta)
        self.assertTrue(ok_corrigir)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "123.456 - Parafuso")))


if __name__ == "__main__":
    unittest.main()
