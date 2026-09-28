"""
Testes de Integração para Armazenamento e Controle de Revisão.
"""

import os
import shutil
import tempfile
import unittest
from core.models import PecaInfo, ComponenteItem
from services.storage_service import StorageService
from services.revision_service import RevisionService


class TestStorageAndRevision(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="controle_cad_test_")
        self.storage = StorageService(self.temp_dir)
        self.revision = RevisionService(self.storage)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_criar_estrutura_peca(self):
        peca = PecaInfo(
            codigo="250.001",
            nome="Parafuso",
            descricao="Parafuso M8",
            tipo="Peça",
            revisao_atual="A"
        )
        sucesso, caminho = self.storage.criar_estrutura_peca(peca)
        self.assertTrue(sucesso)
        self.assertTrue(os.path.exists(caminho))

        # Verifica subpastas obrigatórias
        for sub in ["CAD", "DESENHO", "PDF", "HISTORICO"]:
            self.assertTrue(os.path.isdir(os.path.join(caminho, sub)))

        # Verifica controle.json
        json_path = os.path.join(caminho, "controle.json")
        self.assertTrue(os.path.exists(json_path))

        # Carrega peça novamente
        peca_carregada = self.storage.carregar_peca_por_pasta(caminho)
        self.assertIsNotNone(peca_carregada)
        self.assertEqual(peca_carregada.codigo, "250.001")
        self.assertEqual(peca_carregada.nome, "Parafuso")
        self.assertEqual(peca_carregada.revisao_atual, "A")

    def test_bloqueio_duplicidade_de_pasta(self):
        peca = PecaInfo(codigo="250.001", nome="Parafuso")
        sucesso1, _ = self.storage.criar_estrutura_peca(peca)
        self.assertTrue(sucesso1)

        # Tentativa de recriar a mesma peça
        sucesso2, msg = self.storage.criar_estrutura_peca(peca)
        self.assertFalse(sucesso2)
        self.assertIn("já existe", msg)

    def test_fluxo_nova_revisao(self):
        peca = PecaInfo(codigo="250.001", nome="Parafuso", revisao_atual="A")
        self.storage.criar_estrutura_peca(peca)

        # Simula a criação de arquivos ativos de trabalho
        caminho_cad = os.path.join(peca.pasta_path, "CAD", "250.001.SLDPRT")
        with open(caminho_cad, "w") as f:
            f.write("CONTEUDO_REV_A")

        caminho_des = os.path.join(peca.pasta_path, "DESENHO", "250.001.SLDDRW")
        with open(caminho_des, "w") as f:
            f.write("DESENHO_REV_A")

        # 1. Tenta criar revisão sem motivo (deve falhar)
        ok_sem_motivo, _, msg_erro = self.revision.criar_nova_revisao(peca, motivo="")
        self.assertFalse(ok_sem_motivo)
        self.assertEqual(peca.revisao_atual, "A")

        # 2. Cria revisão com motivo válido
        ok, nova_rev, msg = self.revision.criar_nova_revisao(
            peca=peca,
            motivo="Alteração do comprimento de 30 para 35 mm",
            usuario="Arthur"
        )
        self.assertTrue(ok)
        self.assertEqual(nova_rev, "B")
        self.assertEqual(peca.revisao_atual, "B")

        # 3. Verifica se o histórico da Rev A foi criado
        pasta_rev_a = os.path.join(peca.pasta_path, "HISTORICO", "REV_A")
        self.assertTrue(os.path.isdir(pasta_rev_a))
        self.assertTrue(os.path.exists(os.path.join(pasta_rev_a, "250.001.SLDPRT")))
        self.assertTrue(os.path.exists(os.path.join(pasta_rev_a, "250.001.SLDDRW")))

        # 4. Verifica se o arquivo ativo de trabalho NÃO teve o nome modificado!
        self.assertTrue(os.path.exists(caminho_cad))
        self.assertEqual(os.path.basename(caminho_cad), "250.001.SLDPRT")

        # 5. Verifica se o controle.json foi atualizado
        peca_recarregada = self.storage.carregar_peca_por_pasta(peca.pasta_path)
        self.assertEqual(peca_recarregada.revisao_atual, "B")
        self.assertEqual(len(peca_recarregada.historico), 2)
        self.assertEqual(peca_recarregada.historico[-1].revisao, "B")
        self.assertEqual(peca_recarregada.historico[-1].motivo, "Alteração do comprimento de 30 para 35 mm")

    def test_excluir_peca_e_todas_as_pastas(self):
        """Testa se a exclusão apaga a pasta principal e todas as subpastas (CAD, DESENHO, PDF, HISTORICO)."""
        peca = PecaInfo(
            codigo="250.002",
            nome="Suporte Angular",
            descricao="Suporte de Fixação",
            tipo="Peça",
            revisao_atual="A"
        )
        sucesso_criacao, pasta_criada = self.storage.criar_estrutura_peca(peca)
        self.assertTrue(sucesso_criacao)
        self.assertTrue(os.path.exists(pasta_criada))

        # Adiciona arquivos simulados nas subpastas
        caminho_cad = os.path.join(pasta_criada, "CAD", "250.002.SLDPRT")
        with open(caminho_cad, "w") as f:
            f.write("DADOS_CAD")

        caminho_des = os.path.join(pasta_criada, "DESENHO", "250.002.SLDDRW")
        with open(caminho_des, "w") as f:
            f.write("DADOS_DESENHO")

        caminho_pdf = os.path.join(pasta_criada, "PDF", "250.002.pdf")
        with open(caminho_pdf, "w") as f:
            f.write("DADOS_PDF")

        pasta_rev = os.path.join(pasta_criada, "HISTORICO", "REV_A")
        os.makedirs(pasta_rev, exist_ok=True)
        with open(os.path.join(pasta_rev, "250.002.SLDPRT"), "w") as f:
            f.write("DADOS_REV_A")

        caminho_prev = os.path.join(pasta_criada, "preview.png")
        with open(caminho_prev, "w") as f:
            f.write("DADOS_PREVIEW")

        # Verifica se todas as pastas e arquivos estão presentes
        self.assertTrue(os.path.isdir(os.path.join(pasta_criada, "CAD")))
        self.assertTrue(os.path.isdir(os.path.join(pasta_criada, "DESENHO")))
        self.assertTrue(os.path.isdir(os.path.join(pasta_criada, "PDF")))
        self.assertTrue(os.path.isdir(os.path.join(pasta_criada, "HISTORICO")))
        self.assertTrue(os.path.exists(os.path.join(pasta_criada, "controle.json")))

        # Executa a exclusão completa
        sucesso_exclusao, msg = self.storage.excluir_peca(peca)
        self.assertTrue(sucesso_exclusao)
        self.assertIn("excluídos com sucesso", msg)

        # Garante que a pasta e todas as subpastas não existem mais no disco
        self.assertFalse(os.path.exists(pasta_criada))
        self.assertFalse(os.path.exists(os.path.join(pasta_criada, "CAD")))
        self.assertFalse(os.path.exists(os.path.join(pasta_criada, "DESENHO")))
        self.assertFalse(os.path.exists(os.path.join(pasta_criada, "PDF")))
        self.assertFalse(os.path.exists(os.path.join(pasta_criada, "HISTORICO")))

        # Verifica se não aparece mais na listagem
        todas = self.storage.listar_todas_pecas()
        codigos = [p.codigo for p in todas]
        self.assertNotIn("250.002", codigos)

    def test_excluir_peca_trava_seguranca_pasta_raiz(self):
        """Testa se as travas de segurança impedem exclusão indevida da pasta raiz ou fora dela."""
        # Tentativa de excluir a própria pasta raiz
        peca_invalida = PecaInfo(codigo="000.000", nome="Raiz", pasta_path=self.temp_dir)
        sucesso, msg = self.storage.excluir_peca(peca_invalida)
        self.assertFalse(sucesso)
        self.assertIn("pasta raiz", msg)

        # Tentativa de excluir caminho fora da pasta raiz (ex: pasta pai)
        pasta_externa = os.path.dirname(self.temp_dir)
        peca_externa = PecaInfo(codigo="999.999", nome="Fora", pasta_path=pasta_externa)
        sucesso_ext, msg_ext = self.storage.excluir_peca(peca_externa)
        self.assertFalse(sucesso_ext)
        self.assertIn("fora da pasta raiz", msg_ext)

    def test_excluir_peca_com_arquivos_somente_leitura(self):
        """Testa se arquivos com flag de somente-leitura (comum no Windows) são excluídos com sucesso."""
        import stat
        peca = PecaInfo(codigo="250.003", nome="Pino Trava")
        self.storage.criar_estrutura_peca(peca)

        caminho_bloqueado = os.path.join(peca.pasta_path, "CAD", "250.003.SLDPRT")
        with open(caminho_bloqueado, "w") as f:
            f.write("BLOQUEADO")
        # Define arquivo como somente leitura
        os.chmod(caminho_bloqueado, stat.S_IREAD)

        sucesso, msg = self.storage.excluir_peca(peca)
        self.assertTrue(sucesso)
        self.assertFalse(os.path.exists(peca.pasta_path))

    def test_criar_estrutura_componente_co(self):
        """Verifica a criação da estrutura padronizada para componentes do tipo CO (CO-0000)."""
        peca = PecaInfo(
            codigo="CO-0001",
            nome="Rolamento 608ZZ",
            descricao="Rolamento de esferas 8x22x7",
            tipo="CO",
            revisao_atual="A"
        )
        sucesso, caminho = self.storage.criar_estrutura_peca(peca)
        self.assertTrue(sucesso)
        self.assertTrue(os.path.exists(caminho))
        self.assertTrue(caminho.endswith("CO-0001 - Rolamento 608ZZ"))

        # Verifica subpastas obrigatórias
        for sub in ["CAD", "DESENHO", "PDF", "HISTORICO"]:
            self.assertTrue(os.path.isdir(os.path.join(caminho, sub)))

        # Verifica controle.json
        peca_carregada = self.storage.carregar_peca_por_pasta(caminho)
        self.assertIsNotNone(peca_carregada)
        self.assertEqual(peca_carregada.codigo, "CO-0001")
        self.assertEqual(peca_carregada.tipo, "CO")
        self.assertEqual(peca_carregada.nome, "Rolamento 608ZZ")

    def test_rejeicao_codigo_invalido_ao_criar_co(self):
        """Garante que códigos no formato inválido são rejeitados na criação do tipo CO."""
        peca_invalida = PecaInfo(
            codigo="CO-123",  # 3 dígitos em vez de 4
            nome="Rolamento Inválido",
            tipo="CO"
        )
        sucesso, msg = self.storage.criar_estrutura_peca(peca_invalida)
        self.assertFalse(sucesso)
        self.assertIn("CO-0000", msg)

        # Código de formato normal 000.000 também não pode ser cadastrado como CO
        peca_formato_normal = PecaInfo(
            codigo="250.001",
            nome="Componente com código normal",
            tipo="CO"
        )
        sucesso2, msg2 = self.storage.criar_estrutura_peca(peca_formato_normal)
        self.assertFalse(sucesso2)
        self.assertIn("CO-0000", msg2)

    def test_montagem_com_componentes_co(self):
        """Testa o cadastro e persistência de componentes CO vinculados a uma montagem."""
        # Cria componentes CO no armazenamento
        co1 = PecaInfo(codigo="CO-0001", nome="Rolamento 608ZZ", tipo="CO")
        co2 = PecaInfo(codigo="CO-0002", nome="Anel Trava", tipo="CO")
        self.storage.criar_estrutura_peca(co1)
        self.storage.criar_estrutura_peca(co2)

        # Verifica listagem de COs
        todos_cos = self.storage.obter_todos_cos()
        self.assertEqual(len(todos_cos), 2)
        codigos_cos = [c.codigo for c in todos_cos]
        self.assertIn("CO-0001", codigos_cos)
        self.assertIn("CO-0002", codigos_cos)

        # Cria Montagem vinculando os componentes
        montagem = PecaInfo(
            codigo="100.001",
            nome="Conjunto Cabeçote",
            tipo="Montagem",
            revisao_atual="A",
            componentes=[
                ComponenteItem(codigo="CO-0001", nome="Rolamento 608ZZ", quantidade=2),
                ComponenteItem(codigo="CO-0002", nome="Anel Trava", quantidade=4),
            ]
        )

        sucesso, pasta_montagem = self.storage.criar_estrutura_peca(montagem)
        self.assertTrue(sucesso)

        # Recarrega a montagem e confere os componentes vinculados
        montagem_carregada = self.storage.carregar_peca_por_pasta(pasta_montagem)
        self.assertIsNotNone(montagem_carregada)
        self.assertEqual(montagem_carregada.codigo, "100.001")
        self.assertEqual(montagem_carregada.tipo, "Montagem")
        self.assertEqual(len(montagem_carregada.componentes), 2)

        comp1 = montagem_carregada.componentes[0]
        self.assertEqual(comp1.codigo, "CO-0001")
        self.assertEqual(comp1.nome, "Rolamento 608ZZ")
        self.assertEqual(comp1.quantidade, 2)

        comp2 = montagem_carregada.componentes[1]
        self.assertEqual(comp2.codigo, "CO-0002")
        self.assertEqual(comp2.nome, "Anel Trava")
        self.assertEqual(comp2.quantidade, 4)

    def test_peca_com_multiplos_kits_e_listagem(self):
        """Testa o cadastro, persistência e agregação de kits em peças e montagens."""
        # 1. Cria um torquímetro que é uma Montagem com COs e faz parte de 2 kits
        torquimetro = PecaInfo(
            codigo="200.001",
            nome="Torquímetro Cirúrgico",
            tipo="Montagem",
            revisao_atual="A",
            kits=["Kit Cirúrgico", "Kit Implante"]
        )
        sucesso, pasta_torquimetro = self.storage.criar_estrutura_peca(torquimetro)
        self.assertTrue(sucesso)

        # 2. Cria outra peça que faz parte de um kit em comum e outro kit novo
        chave = PecaInfo(
            codigo="200.002",
            nome="Chave Catraca",
            tipo="Peça",
            revisao_atual="A",
            kits=["Kit Cirúrgico", "Kit Prótese"]
        )
        sucesso_ch, pasta_chave = self.storage.criar_estrutura_peca(chave)
        self.assertTrue(sucesso_ch)

        # 3. Recarrega o torquímetro do disco e valida seus kits
        torq_carregado = self.storage.carregar_peca_por_pasta(pasta_torquimetro)
        self.assertIsNotNone(torq_carregado)
        self.assertEqual(len(torq_carregado.kits), 2)
        self.assertIn("Kit Cirúrgico", torq_carregado.kits)
        self.assertIn("Kit Implante", torq_carregado.kits)

        # 4. Testa obter_todos_kits: deve retornar lista única ordenada de kits
        todos_kits = self.storage.obter_todos_kits()
        self.assertEqual(todos_kits, ["Kit Cirúrgico", "Kit Implante", "Kit Prótese"])

        # 5. Adiciona o torquímetro a mais um kit e salva
        torq_carregado.kits.append("Kit Ortognática")
        ok_salvar = self.storage.salvar_controle_json(torq_carregado)
        self.assertTrue(ok_salvar)

        # Recarrega e confirma o novo kit
        torq_atualizado = self.storage.carregar_peca_por_pasta(pasta_torquimetro)
        self.assertEqual(len(torq_atualizado.kits), 3)
        self.assertIn("Kit Ortognática", torq_atualizado.kits)

        # Valida que obter_todos_kits agora inclui o novo kit
        todos_kits_atualizado = self.storage.obter_todos_kits()
        self.assertIn("Kit Ortognática", todos_kits_atualizado)
        self.assertEqual(len(todos_kits_atualizado), 4)

    def test_catalogo_kits_crud(self):
        """Testa o cadastro global, renomeação, exclusão e vínculo de peças no catálogo de kits."""
        # 1. Cadastrar kits
        ok1, _ = self.storage.cadastrar_kit("Kit Coluna", "Instrumentais de coluna vertebral")
        self.assertTrue(ok1)

        ok2, _ = self.storage.cadastrar_kit("Kit Joelho", "Prótese de joelho")
        self.assertTrue(ok2)

        # Bloqueio de duplicidade
        ok_dup, msg_dup = self.storage.cadastrar_kit("Kit Coluna")
        self.assertFalse(ok_dup)
        self.assertIn("Já existe", msg_dup)

        # Bloqueio de nome vazio
        ok_vazio, _ = self.storage.cadastrar_kit("   ")
        self.assertFalse(ok_vazio)

        # 2. Obter catálogo
        cat = self.storage.obter_catalogo_kits()
        nomes_cat = [k["nome"] for k in cat]
        self.assertIn("Kit Coluna", nomes_cat)
        self.assertIn("Kit Joelho", nomes_cat)

        # 3. Criar peça e vincular ao kit
        peca = PecaInfo(codigo="500.001", nome="Placa Cervical")
        self.storage.criar_estrutura_peca(peca)

        ok_vinc = self.storage.vincular_peca_a_kit("500.001", "Kit Coluna")
        self.assertTrue(ok_vinc)

        pecas_kit = self.storage.obter_pecas_do_kit("Kit Coluna")
        self.assertEqual(len(pecas_kit), 1)
        self.assertEqual(pecas_kit[0].codigo, "500.001")

        # 4. Renomear kit: deve atualizar catálogo e a peça vinculada
        ok_ren, _ = self.storage.renomear_kit("Kit Coluna", "Kit Coluna Avançado")
        self.assertTrue(ok_ren)

        cat_atualizado = self.storage.obter_catalogo_kits()
        nomes_ren = [k["nome"] for k in cat_atualizado]
        self.assertIn("Kit Coluna Avançado", nomes_ren)
        self.assertNotIn("Kit Coluna", nomes_ren)

        peca_rec = self.storage.carregar_peca_por_pasta(peca.pasta_path)
        self.assertIn("Kit Coluna Avançado", peca_rec.kits)
        self.assertNotIn("Kit Coluna", peca_rec.kits)

        # 5. Desvincular peça
        ok_desv = self.storage.desvincular_peca_de_kit("500.001", "Kit Coluna Avançado")
        self.assertTrue(ok_desv)
        pecas_depois = self.storage.obter_pecas_do_kit("Kit Coluna Avançado")
        self.assertEqual(len(pecas_depois), 0)

        # 6. Excluir kit
        ok_exc, _ = self.storage.excluir_kit("Kit Joelho")
        self.assertTrue(ok_exc)
        cat_final = self.storage.obter_catalogo_kits()
        nomes_final = [k["nome"] for k in cat_final]
        self.assertNotIn("Kit Joelho", nomes_final)

    def test_linhas_produto_e_kits(self):
        """Testa o suporte a múltiplas linhas de produto (MedicalFix, DentFix, TraumaFix) e kits associados."""
        # 1. Cadastro de kits em linhas específicas
        ok_d, _ = self.storage.cadastrar_kit("Kit Guiado", "Kit cirúrgico odontológico", linha="DentFix")
        self.assertTrue(ok_d)

        ok_m, _ = self.storage.cadastrar_kit("Kit Buco 2.0", "Placas e parafusos bucomaxilo", linha="MedicalFix")
        self.assertTrue(ok_m)

        ok_t, _ = self.storage.cadastrar_kit("Kit Trauma Fêmur", "Hastes intramedulares", linha="TraumaFix")
        self.assertTrue(ok_t)

        # Kit genérico (Todas as Linhas)
        ok_g, _ = self.storage.cadastrar_kit("Kit Universal Chaves", "Instrumentais universais", linha="")
        self.assertTrue(ok_g)

        # 2. Filtragem de catálogo por linha de produto
        cat_dent = self.storage.obter_catalogo_kits(linha="DentFix")
        nomes_dent = [k["nome"] for k in cat_dent]
        self.assertIn("Kit Guiado", nomes_dent)
        self.assertIn("Kit Universal Chaves", nomes_dent)
        self.assertNotIn("Kit Buco 2.0", nomes_dent)
        self.assertNotIn("Kit Trauma Fêmur", nomes_dent)

        cat_med = self.storage.obter_catalogo_kits(linha="MedicalFix")
        nomes_med = [k["nome"] for k in cat_med]
        self.assertIn("Kit Buco 2.0", nomes_med)
        self.assertIn("Kit Universal Chaves", nomes_med)
        self.assertNotIn("Kit Guiado", nomes_med)

        # 3. Filtragem de todos os nomes de kits por linha
        kits_dent_nomes = self.storage.obter_todos_kits(linha="DentFix")
        self.assertIn("Kit Guiado", kits_dent_nomes)
        self.assertIn("Kit Universal Chaves", kits_dent_nomes)
        self.assertNotIn("Kit Buco 2.0", kits_dent_nomes)

        # 4. Criar peça vinculada à linha DentFix e verificar persistência
        peca_dent = PecaInfo(
            codigo="300.001",
            nome="Guia Cirúrgico Estreito",
            tipo="Peça",
            linha_produto="DentFix",
            kits=["Kit Guiado"]
        )
        sucesso, pasta_dent = self.storage.criar_estrutura_peca(peca_dent)
        self.assertTrue(sucesso)

        peca_carregada = self.storage.carregar_peca_por_pasta(pasta_dent)
        self.assertIsNotNone(peca_carregada)
        self.assertEqual(peca_carregada.linha_produto, "DentFix")
        self.assertIn("Kit Guiado", peca_carregada.kits)

        # 5. Criar peça sem linha explícita - deve assumir padrão MedicalFix
        peca_padrao = PecaInfo(
            codigo="300.002",
            nome="Placa Reta 4 Furos",
            tipo="Peça"
        )
        self.assertEqual(peca_padrao.linha_produto, "MedicalFix")
        sucesso_p, pasta_padrao = self.storage.criar_estrutura_peca(peca_padrao)
        self.assertTrue(sucesso_p)

        peca_p_carregada = self.storage.carregar_peca_por_pasta(pasta_padrao)
        self.assertEqual(peca_p_carregada.linha_produto, "MedicalFix")

        # 6. Alterar linha de um kit existente usando editar_kit
        ok_edit, _ = self.storage.editar_kit(
            nome_antigo="Kit Trauma Fêmur",
            nome_novo="Kit Trauma Fêmur Avançado",
            descricao_nova="Nova descrição",
            linha_nova="MedicalFix"
        )
        self.assertTrue(ok_edit)

        # Agora o kit deve aparecer em MedicalFix e não mais em TraumaFix
        cat_med_pos = self.storage.obter_catalogo_kits(linha="MedicalFix")
        nomes_med_pos = [k["nome"] for k in cat_med_pos]
        self.assertIn("Kit Trauma Fêmur Avançado", nomes_med_pos)

        cat_trauma_pos = self.storage.obter_catalogo_kits(linha="TraumaFix")
        nomes_trauma_pos = [k["nome"] for k in cat_trauma_pos]
        self.assertNotIn("Kit Trauma Fêmur Avançado", nomes_trauma_pos)


if __name__ == "__main__":
    unittest.main()




