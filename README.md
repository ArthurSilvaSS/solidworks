# Controle CAD — Gerenciador Simples de Projetos SolidWorks

Aplicativo Windows leve e ágil desenvolvido para equipes de engenharia (projetistas), com foco em:
1. **Padronização rigorosa** de pastas e arquivos (`000.000 - Nome da Peça`);
2. **Prevenção ativa de duplicidade** (por código, similaridade de termos e hash binário);
3. **Controle de revisões simples e confiável** (com arquivamento automático em `HISTORICO\REV_X` e preservação dos arquivos de trabalho ativos).

---

## Filosofia do Sistema
> **"O projetista trabalha no SolidWorks. O Controle CAD cuida da organização."**

---

## 🛠️ Tecnologias Utilizadas
- **Linguagem:** Python 3.14+ (Compatível com Windows 10 e 11)
- **Interface Gráfica:** CustomTkinter (Visual moderno, suporte a temas Claro/Escuro, High DPI)
- **Integração CAD:** API COM oficial do SolidWorks (`SldWorks.Application` via `pywin32`)
- **Metadados:** Arquivos locais `controle.json` por pasta (portabilidade total)
- **Auditoria:** `controle_cad.log` com identificação do usuário Windows

---

## 📁 Estrutura de Arquivos e Pastas

### Padrão da Pasta Raiz (Servidor/Rede)
A pasta raiz pode ser uma pasta local ou caminho de rede UNC (`\\SERVIDOR\ENGENHARIA`).

Dentro dela, cada projeto segue estritamente:
```text
250.001 - Parafuso
├── CAD/
│   └── 250.001.SLDPRT (ou .SLDASM)
├── DESENHO/
│   └── 250.001.SLDDRW
├── PDF/
│   └── 250.001.pdf
├── HISTORICO/
│   └── REV_A/
│       ├── 250.001.SLDPRT
│       ├── 250.001.SLDDRW
│       └── 250.001.pdf
└── controle.json
```

---

## 🚀 Como Executar

### 1. Instalação das Dependências
No terminal / PowerShell, execute:
```bash
pip install -r requirements.txt
```

### 2. Iniciar o Aplicativo
```bash
python main.py
```

---

## ⚙️ Funcionalidades Principais

### 1. ➕ Nova Peça / Componente (CO) / Montagem
- Suporte a múltiplos tipos de engenharia:
  - **Peça:** formato de código rigoroso `000.000` (ex: `250.001`).
  - **Montagem:** formato de código rigoroso `000.000` (ex: `100.001`).
  - **CO (Componente):** abreviação de componente, formato estrito **`CO-0000`** (prefixo `CO-` seguido de exatamente 4 dígitos, ex: `CO-0001`).
- **Validação Dinâmica no Modal:** ao selecionar o tipo **CO**, o campo de código e os rótulos de orientação alternam automaticamente para o padrão `CO-0000` (ex: `CO-0001`).
- **Vínculo de Componentes (COs) na Montagem:**
  - Ao criar uma **Montagem**, o sistema pergunta ativamente quais componentes (CO) comprados fazem parte daquela montagem.
  - O modal interativo permite selecionar componentes existentes, definir quantidades e até cadastrar novos COs rapidamente.
  - Os componentes vinculados são salvos no `controle.json`, gravados como Custom Property (`COMPONENTES_CO`) no arquivo de montagem `.SLDASM`, e exibidos com detalhes no painel da aplicação.
  - A qualquer momento, é possível visualizar ou atualizar a lista de COs de uma montagem através do botão **`📦 Componentes (CO)`** ou pelo menu de contexto (botão direito).
- **Bloqueio de Duplicidade:** Impede cadastrar um código já existente e oferece abrir a pasta atual.
- **Alerta de Similaridade:** Detecta se já existem peças com nomes parecidos (ex: *Parafuso M8 x 35* vs *Parafuso M8 x 20*) alertando o projetista antes de criar.
- **Criação e Configuração Automática:** Cria as pastas `CAD`, `DESENHO`, `PDF`, `HISTORICO` e o arquivo `controle.json` (tanto para `000.000 - Nome` quanto `CO-0000 - Nome`).
- **Abertura Imediata no SolidWorks:** Conecta ao SolidWorks, cria o modelo 3D (`.SLDPRT` ou `.SLDASM`), grava as *Custom Properties* (`CODIGO`, `DESCRICAO`, `REVISAO=A`, `TIPO`) e já salva diretamente na pasta `CAD`. O projetista já inicia modelando sem se preocupar com pastas ou nomes.

### 2. 📝 Criar / Abrir Desenho 2D (Salvar sem pedir pasta)
- Ao clicar em **`📝 Criar / Abrir Desenho`**, o sistema cria o desenho 2D (`.SLDDRW`) a partir do template padrão (`Desenho.DRWDOT`), vincula ao modelo 3D correspondente, grava as *Custom Properties* e já **salva automaticamente em `DESENHO\<CODIGO>.SLDDRW`**.
- Como o arquivo já possui caminho fixo e oficial, ao detalhar a peça no SolidWorks e pressionar **Salvar (Ctrl+S)**, ele salva diretamente no arquivo **sem jamais abrir janelas de seleção de pasta**.

### 3. 🖨️ Geração e Sincronização 100% Automática de PDF
- **Detecção Inteligente:** O sistema monitora a pasta de projetos e identifica automaticamente quando uma peça já possui o modelo 3D (`CAD`) e a prancha de detalhamento 2D (`DESENHO`).
- **Geração Autônoma em Segundo Plano:** Se o arquivo PDF estiver ausente, o sistema exporta o `.pdf` sozinho e diretamente para a pasta `PDF\<CODIGO>.pdf` sem necessidade de clique manual.
- **Detecção de Alterações (Auto-Update):** Se o projetista alterar e salvar o desenho `.SLDDRW` no SolidWorks, o sistema detecta que o desenho é mais recente que o PDF e regera o PDF automaticamente.
- **Geração Imediata ao Criar Desenho:** Ao criar um novo desenho 2D pela aplicação, o PDF correspondente já é gerado e disponibilizado de imediato.
- **Painel e Badges Visuais:** Exibe etiquetas em tempo real (`PDF ✓`, `PDF ⚡`, `PDF ⏳`) na Galeria 3D e na Tabela, além do botão de ação **`⚡ SINCRONIZAR PDFs`**.


### 4. ↻ Nova Revisão
- Exige o preenchimento do **motivo da alteração**.
- Copia o estado atual dos arquivos para `HISTORICO\REV_<atual>\`.
- **Preservação do nome:** O arquivo de trabalho na pasta `CAD` **não muda de nome** (continua `250.001.SLDPRT`), evitando perda de referências e confusão com arquivos do tipo `_FINAL` ou `_REV_B`.
- Atualiza a propriedade `REVISAO` no SolidWorks e no `controle.json`.

### 5. ✓ Validar Projetos
Varre a pasta de engenharia e detecta:
- Pastas fora do padrão (`123456 - Parafuso`, `ABC - Teste`);
- Arquivos com sufixos proibidos (`250.001_FINAL.SLDPRT`);
- Inconsistências de código;
- Subpastas faltantes.
- Permite **correção automática** para pastas com formato recuperável (ex: `123456 - Parafuso` ➔ `123.456 - Parafuso` e `CO1234 - Rolamento` ➔ `CO-1234 - Rolamento`).

### 6. 🔎 Painel de Ações Rápidas e Menu de Contexto
- Busca em tempo real por código, nome e descrição;
- Botões diretos no painel inferior e menu de contexto (botão direito do mouse nas peças):
  - `📐 Abrir CAD` (abre o modelo 3D no SolidWorks)
  - `📝 Criar / Abrir Desenho` (cria/abre o `.SLDDRW` já salvo no SolidWorks)
  - `🖨️ Gerar PDF` (exporta PDF a partir do desenho via SolidWorks)
  - `📄 Abrir PDF` (abre o PDF no visualizador padrão)
  - `📁 Abrir Pasta` (abre o Windows Explorer no diretório do projeto)
  - `📜 Histórico` (exibe histórico detalhado de revisões)
  - `🗑️ Excluir` (exclui o desenho e remove todas as pastas vinculadas: `CAD`, `DESENHO`, `PDF`, `HISTORICO` e `controle.json` com modal de confirmação seguro e atalho pela tecla `Delete`).


---

## 🧪 Testes Automatizados
Para executar a suíte completa de testes:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
