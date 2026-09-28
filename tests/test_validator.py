"""
Testes Unitários para Validações e Regras de Nomenclatura do Controle CAD.
"""

import unittest
from core.validator import (
    validar_codigo,
    validar_nome_peca,
    validar_nome_pasta,
    sugerir_correcao_pasta,
    validar_nome_arquivo_cad,
    proxima_revisao
)


class TestValidator(unittest.TestCase):
    def test_validar_codigo_valido(self):
        codigos_validos = ["250.001", "123.456", "001.002", "000.000", "999.999"]
        for cod in codigos_validos:
            valido, msg = validar_codigo(cod)
            self.assertTrue(valido, f"Código deveria ser válido: {cod}. Msg: {msg}")

    def test_validar_codigo_co_valido(self):
        codigos_co = ["CO-0001", "CO-0000", "CO-9999", "CO-1234", "co-0500"]
        for cod in codigos_co:
            valido, msg = validar_codigo(cod, tipo="CO")
            self.assertTrue(valido, f"Código CO deveria ser válido: {cod}. Msg: {msg}")
            # Sem tipo especificado também deve aceitar pelo padrão CO
            val_auto, _ = validar_codigo(cod)
            self.assertTrue(val_auto, f"Código CO auto-detectado deveria ser válido: {cod}")

    def test_validar_codigo_co_invalido(self):
        codigos_co_invalidos = [
            "CO-001",       # 3 dígitos em vez de 4
            "CO-00001",     # 5 dígitos
            "CO1234",       # sem hífen
            "CO_1234",      # underline em vez de hífen
            "CO-ABCD",      # letras após hífen
            "CO-12A4",      # letra no meio
            "CO-",          # sem dígitos
            "250.001",      # formato padrão não permitido quando tipo é CO
        ]
        for cod in codigos_co_invalidos:
            valido, msg = validar_codigo(cod, tipo="CO")
            self.assertFalse(valido, f"Código CO deveria ser inválido: {cod}")

    def test_validar_codigo_com_tipo(self):
        # Peça exige 000.000
        self.assertTrue(validar_codigo("250.001", tipo="Peça")[0])
        self.assertFalse(validar_codigo("CO-0001", tipo="Peça")[0])

        # Montagem exige 000.000
        self.assertTrue(validar_codigo("250.001", tipo="Montagem")[0])
        self.assertFalse(validar_codigo("CO-0001", tipo="Montagem")[0])

        # CO exige CO-0000
        self.assertTrue(validar_codigo("CO-0001", tipo="CO")[0])
        self.assertFalse(validar_codigo("250.001", tipo="CO")[0])

    def test_validar_codigo_invalido(self):
        codigos_invalidos = [
            "250001",      # sem ponto
            "25.001",      # 2 números no início
            "250.01",      # 2 números no final
            "250-001",     # traço em vez de ponto
            "ABC.001",     # letras
            "250.001a",    # letra no final
            "",            # vazio
            "   ",         # espaços
        ]
        for cod in codigos_invalidos:
            valido, msg = validar_codigo(cod)
            self.assertFalse(valido, f"Código deveria ser inválido: {cod}")

    def test_validar_nome_peca(self):
        # Válidos
        self.assertTrue(validar_nome_peca("Parafuso")[0])
        self.assertTrue(validar_nome_peca("Suporte Motor M8")[0])
        self.assertTrue(validar_nome_peca("Eixo Principal - 100mm")[0])

        # Inválidos
        self.assertFalse(validar_nome_peca("")[0])
        self.assertFalse(validar_nome_peca("A")[0])  # Muito curto
        self.assertFalse(validar_nome_peca("Parafuso/M8")[0])  # Caractere proibido
        self.assertFalse(validar_nome_peca("Peça:Nova")[0])   # Caractere proibido

    def test_validar_nome_pasta(self):
        # Formato padrão 000.000
        valido, cod, nome = validar_nome_pasta("250.001 - Parafuso")
        self.assertTrue(valido)
        self.assertEqual(cod, "250.001")
        self.assertEqual(nome, "Parafuso")

        # Formato CO-0000
        valido_co, cod_co, nome_co = validar_nome_pasta("CO-0001 - Rolamento 608ZZ")
        self.assertTrue(valido_co)
        self.assertEqual(cod_co, "CO-0001")
        self.assertEqual(nome_co, "Rolamento 608ZZ")

        valido, cod, nome = validar_nome_pasta("Parafuso")
        self.assertFalse(valido)

        valido, cod, nome = validar_nome_pasta("250001 - Parafuso")
        self.assertFalse(valido)

    def test_sugerir_correcao_pasta(self):
        sugestao = sugerir_correcao_pasta("123456 - Parafuso")
        self.assertEqual(sugestao, "123.456 - Parafuso")

        sugestao = sugerir_correcao_pasta("250001 - Suporte")
        self.assertEqual(sugestao, "250.001 - Suporte")

        sugestao_co = sugerir_correcao_pasta("CO1234 - Rolamento")
        self.assertEqual(sugestao_co, "CO-1234 - Rolamento")

        # Não corrigível automaticamente se não tiver padrão reconhecível
        self.assertIsNone(sugerir_correcao_pasta("ABC - Suporte"))

    def test_validar_nome_arquivo_cad(self):
        # Válidos
        self.assertTrue(validar_nome_arquivo_cad("250.001.SLDPRT", "250.001")[0])
        self.assertTrue(validar_nome_arquivo_cad("250.001.SLDASM", "250.001")[0])
        self.assertTrue(validar_nome_arquivo_cad("250.001.SLDDRW", "250.001")[0])
        self.assertTrue(validar_nome_arquivo_cad("250.001.pdf", "250.001")[0])

        # Inválidos por conter revisão no nome
        self.assertFalse(validar_nome_arquivo_cad("250.001_REV_A.SLDPRT", "250.001")[0])
        self.assertFalse(validar_nome_arquivo_cad("250.001_FINAL.SLDPRT", "250.001")[0])
        self.assertFalse(validar_nome_arquivo_cad("250.001_NOVO.SLDPRT", "250.001")[0])

        # Inconsistência de código
        val, msg = validar_nome_arquivo_cad("250.002.SLDPRT", "250.001")
        self.assertFalse(val)
        self.assertIn("código", msg)

    def test_proxima_revisao(self):
        self.assertEqual(proxima_revisao("A"), "B")
        self.assertEqual(proxima_revisao("B"), "C")
        self.assertEqual(proxima_revisao("Y"), "Z")
        self.assertEqual(proxima_revisao("Z"), "AA")
        self.assertEqual(proxima_revisao("AA"), "AB")


if __name__ == "__main__":
    unittest.main()
