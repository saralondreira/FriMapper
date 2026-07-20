# Frimapper — Registo de Projeto e Progresso (Documento Vivo)

> **Propósito.** Documento vivo do planeamento, decisões de arquitetura e,
> sobretudo, do registo contínuo de **problemas encontrados e soluções
> implementadas**. Deve ser atualizado a cada iteração. Destina-se também a ser
> publicado no **SharePoint da empresa** (ver secção *Publicação no SharePoint*).

Última atualização: **2026-07-14**

---

## 1. Visão geral

Aplicação desktop (PySide6) para **mapear a rede de raiz e mantê-la**, com o
SQLite como fonte de verdade única, geração de topologias via `diagrams`
(Graphviz) e *security by design* (RBAC, auditoria, cifra, anti-injeção).

Decisão fundadora: **não** importar os Excels antigos — a informação estava
demasiado dispersa. A aplicação passa a ser a ferramenta de gestão.

## 2. Decisões de arquitetura (e porquê)

**Padrão MVC** (ver #010): **Model** = `db/` + `repositories/` + `services/`;
**Controller** = `gui/controllers/` (gere sessões, orquestra, devolve DTOs);
**View** = `gui/views/` + adaptadores Qt em `gui/models/`. As Views não conhecem
ORM nem BD — só DTOs (`gui/dto.py`).

| Área | Decisão | Racional |
|---|---|---|
| GUI | PySide6 + MVC | Força do `QTableView`/modelos para dados densos; LGPLv3 (uso interno). |
| Persistência | SQLite (arranque) | 1 ficheiro, transacional, standalone. |
| Acesso a dados | SQLAlchemy 2.0 + Repository | DB-agnóstico: migração p/ Postgres/MySQL/MSSQL só muda a connection string. |
| Dependências | Bloqueio na camada Repository + FK na BD | Integridade estrita; override só com password de admin (force cascade, auditado). |
| Segurança | passlib (argon2) · Fernet · audit log · queries parametrizadas | RBAC 3 perfis + data masking ao nível do campo. |
| Mapa | `diagrams` + Graphviz, geração diferida | PNG limpo; interatividade fica nos widgets, não na imagem. |

## 3. Estado atual (progresso por fase)

- **Fase 1 — Núcleo de dados:** ✅ Concluída e testada (21 verificações).
  Modelos ORM, repositórios com dependências, bootstrap, cifra, auditoria.
- **Fase 2 — Serviços:** ✅ Pesquisa global, síntese por nó, export CSV, motor
  de mapa (com vistas full/core/location e alerta de desatualização).
- **Fase 4 — GUI (MVC):** ✅ Estrutura MVC completa. Login, janela principal,
  tabela com masking, síntese por nó, geração de mapa em worker thread, e
  diálogos/separadores CRUD de Equipamentos, Zonas, Templates e Utilizadores,
  com fluxo de force-delete por password de Master. Validado headless (10 checks).
- **Biblioteca de ícones:** ✅ 12 badges Custom (`assets/icons/`) + gerador
  (`tools/make_icons.py`); core usa ícones nativos. Bug de caminho corrigido (#009).
- **Validação end-to-end do mapa:** ✅ PNG real gerado, com clusters, ícones
  (nativos + Custom), link *down* a vermelho tracejado e timestamp no canvas.
- **Fase 5 — Empacotamento (PyInstaller + Graphviz):** ✅ `frimapper.spec`
  (onedir) + `tools/build_windows.ps1`; separação recursos/dados (#013);
  Graphviz empacotável via `GRAPHVIZ_HOME`. Binário validado com `--selftest`.
- **Roadmap (1ª iteração pós-manual):** ✅ Testes de interação `QTest`
  (8 checks, #016); *upload session* SharePoint >4 MB (#017); lock de versões
  `requirements.lock` (#018).
- **v0.2.0 — Janelas CRUD dedicadas:** ✅ Portas (#021), Ligações (listar/
  editar estado/eliminar), catálogo de VLANs (#019), Firewalls (categoria
  trancada + portas WAN), Manutenções com datas (#020) e janela de exportação
  com data e filtro. Testes: 40/16/10.
- **v0.3.0 — Renomeação do pacote:** ✅ `netmap` → `frimapper` (#022), com as
  env vars `NETMAP_*` → `FRIMAPPER_*`. Testes 40/16/10 e bundle revalidados.

## 4. Registo de Problemas Encontrados e Soluções

> Formato: cada entrada tem data, problema, impacto e solução. **Acrescentar
> nova entrada sempre que surgir um problema — não reescrever as antigas.**

### 2026-07-01 · #001 — Graphviz não instalado no ambiente
- **Problema:** a `diagrams` invoca o binário `dot`; ambientes limpos não o têm.
- **Impacto:** *Gerar Mapa* rebentaria com erro críptico.
- **Solução:** import tardio da `diagrams` dentro de `MapService.generate()` e
  `try/except` que converte a falha numa mensagem amigável a pedir a instalação.
  A app arranca e funciona sem Graphviz; só o mapa fica indisponível. Para
  produção: empacotar o Graphviz com PyInstaller (ver #008).

### 2026-07-01 · #002 — Contexto thread-local da `diagrams`
- **Problema:** `with Diagram()` guarda estado em variáveis thread-local; gerar
  o mapa na thread da GUI congela a interface, mas partir o contexto entre
  threads corrompe-o.
- **Solução:** `MapService.generate()` corre **por inteiro** num `QThread`
  dedicado (`_MapWorker`), que abre a sua própria sessão de BD. Documentado no
  cabeçalho de `map_service.py`.

### 2026-07-01 · #003 — FK desligadas por defeito no SQLite
- **Problema:** o SQLite ignora FK a menos que se ative por ligação; sem isto, a
  rede de segurança relacional a nível de BD não existia.
- **Solução:** listener de evento `connect` que executa `PRAGMA foreign_keys=ON`
  (`db/base.py`), aplicado só quando o motor é SQLite.

### 2026-07-01 · #004 — Ordem de inicialização da cifra
- **Problema:** as colunas `EncryptedString` precisam da cifra Fernet; se o
  primeiro acesso à BD acontecer antes de a cifra existir, dá `RuntimeError`.
- **Solução:** `initialize_app()` garante a ordem: carregar/criar chave →
  `EncryptedString.set_cipher()` → criar engine/schema.

### 2026-07-01 · #005 — Ícones industriais inexistentes na `diagrams`
- **Problema:** não há ícones nativos para PLC, CCTV, régua, EV, solar, etc.
- **Solução:** resolução em 3 níveis — PNG `Custom` próprio (`assets/icons/`) →
  ícone nativo mapeado (`NATIVE_FALLBACK`) → nó `Blank`. O mapa fica utilizável
  já; a biblioteca de ícones próprios é trabalho a orçamentar.

### 2026-07-01 · #006 — Fuga de credenciais no export CSV
- **Problema:** ao exportar via ORM, os campos cifrados sairiam **em claro** no
  CSV (um backup legível de passwords é um risco).
- **Solução:** `ExportService` nunca escreve o valor real desses campos —
  substitui por `[protegido]`. Verificado no smoke test.

### 2026-07-01 · #007 — SharePoint sem conector no ambiente de desenvolvimento
- **Problema:** pretende-se publicar a documentação no SharePoint, mas o
  ambiente atual não tem conector Microsoft Graph/SharePoint.
- **Solução (provisória):** a documentação canónica vive no repositório em
  Markdown (portável). Opções de publicação em aberto na secção seguinte.

### 2026-07-01 · #008 — Alojar programa/CSV no SharePoint: separação da chave
- **Contexto:** o SharePoint destina-se a alojar o programa e os backups CSV para
  gestão segura (controlo de acessos + versionamento do portal).
- **Problema (segurança):** se algum dia o `.db` cifrado for para o SharePoint
  **junto** da `secret.key` (chave Fernet), a cifra em repouso deixa de proteger
  — quem acede à biblioteca tem cifra e chave.
- **Solução:** (1) para backup normal usa-se o **CSV**, onde as credenciais já
  saem como `[protegido]` (#006); (2) a chave `secret.key` fica FORA do
  SharePoint (cofre/gestor de segredos ou só na máquina); (3) `client_secret` do
  conector vem de env var, nunca de ficheiro versionado. Conector opcional em
  `netmap/integrations/sharepoint.py` (Graph API), desligado por defeito.
- **Estado:** conector escrito mas NÃO testado neste ambiente (sem tenant);
  validar numa máquina com app registada no Entra ID.

### 2026-07-01 · #009 — Ícones Custom da diagrams renderizavam nós vazios
- **Problema:** os PNG da biblioteca própria (PLC, CCTV…) apareciam em branco no
  mapa, apesar de o ficheiro existir e de o Graphviz suportar imagens.
- **Causa:** o `Custom` recebia um caminho **relativo**; o Graphviz resolve o
  atributo `image=` no contexto de render (não no CWD), logo não encontrava o
  ficheiro e omitia-o em silêncio. Os ícones nativos usam caminhos absolutos.
- **Solução:** `MapService` passa agora `os.path.abspath(...)` ao `Custom`.
  Confirmado com regeneração do mapa (PLC/CAM visíveis).

### 2026-07-01 · #010 — Arquitetura MVC explícita
- **Requisito:** o modelo da aplicação deve ser MVC, para facilidade de acesso.
- **Solução:** introduzida a camada `gui/controllers/` (Auth, Device, Location,
  Template, User, Map, Search, Export). As Views (`gui/views/`) deixaram de
  aceder a BD/repositórios — comunicam por DTOs planos (`gui/dto.py`) e a sessão
  passou a guardar apenas valores (`UserSession` sem ORM). Benefício extra:
  elimina o risco de instâncias ORM destacadas na UI. Validado por `gui_smoke`.

### 2026-07-01 · #011 — Validação do nome "Frimapper"
- **Ação:** pesquisa web + PyPI/GitHub/npm. Não há produto/empresa/pacote com
  esse nome (existem apenas semelhantes: FireMapper, TriMapper, Frimake).
- **Decisão:** nome adotado como `APP_NAME` (constante única em `netmap/__init__`).
  O pacote Python mantém-se `netmap`. **Pendente:** verificação formal de marca
  (EUIPO/INPI) e registo de domínio/PyPI para reservar.

### 2026-07-01 · #012 — Validação headless da GUI (sem display)
- **Problema:** o container não tem display nem libs GL (`libEGL.so.1`), pelo
  que não se conseguia sequer importar o PySide6 para validar a GUI.
- **Solução:** instaladas as libs Qt mínimas + `QT_QPA_PLATFORM=offscreen`;
  criado `tests/gui_smoke.py` que **constrói** janela/tabs/diálogos para os 3
  perfis sem `exec()`. Apanha erros que o `py_compile` não vê.

### 2026-07-01 · #013 — Empacotamento: recursos vs. dados graváveis
- **Problema:** num executável PyInstaller, os recursos ficam em `sys._MEIPASS`
  (temporário, read-only). Escrever a BD/chave/logs aí falharia ou perder-se-ia.
- **Solução:** módulo `netmap/paths.py` separa `resource_dir()` (ícones, etc.)
  de `data_dir()` (BD/chave/logs/mapas → `%APPDATA%/Frimapper` ou `~/.frimapper`,
  override por `FRIMAPPER_DATA`). O `config.load()` passou a usar estes caminhos.
- **Graphviz:** `netmap/runtime.configure_graphviz` coloca no PATH o `dot`
  empacotado (`<recursos>/graphviz/bin`, via `GRAPHVIZ_HOME` no build) ou o
  configurado; caso contrário usa o do sistema.
- **Validação:** build feito com `frimapper.spec`; o binário congelado corre
  `--selftest` (headless) e gera um PNG usando os ícones empacotados. ✅

### 2026-07-01 · #014 — Alerta de equipamentos órfãos após force-delete
- **Requisito:** ao eliminar um equipamento com password de admin (cascade), os
  equipamentos que ficam sem ligação têm de despoletar um alerta para reposição.
- **Solução:** `IntegrityService` calcula os *peers* ligados ANTES do delete e,
  DEPOIS, marca `Device.needs_relink` nos que ficaram sem qualquer link. Os
  controllers (`Device`/`Location`) devolvem os hostnames órfãos. Na GUI:
  (1) popup imediato; (2) **banner laranja persistente**; (3) **linhas destacadas**
  na tabela. Novo botão **"Ligar…"** (`LinkController` + `LinkDialog`, só portas
  livres) permite repor a ligação, o que limpa automaticamente o `needs_relink`.
- **Validação:** smoke test (peer detetado → PC órfão → reposição limpa alerta).

### 2026-07-01 · #015 — Campos dinâmicos por equipamento (EAV)
- **Requisito:** cada equipamento pode precisar de campos diferentes (um switch
  com mais info; num PC: detentor, conta logada, IPs/MACs extra, specs…),
  adicionáveis/removíveis livremente na GUI.
- **Solução:** tabela `DeviceAttribute` (chave-valor, cascade com o equipamento).
  `DeviceRepository.set_attributes` sincroniza (add/update/remove) com auditoria.
  GUI: botão **"Campos…"** → `DeviceAttributesDialog` (tabela editável + sugestões
  comuns). A **pesquisa global** e o **export CSV** passam a incluir os campos
  dinâmicos (`campos_dinamicos.csv`).
- **Nota de segurança:** o editor está atrás da permissão EDIT (Manutenção não
  acede), evitando expor IPs/MACs guardados como campos livres ao perfil com
  masking.

### 2026-07-04 · #016 — GUI validada por construção mas não por interação
- **Problema:** o `gui_smoke.py` constrói janelas/diálogos mas não simula
  cliques nem teclado — regressões em handlers de botões ou em fluxos de
  formulário passariam despercebidas (limitação assinalada no MANUAL §24).
- **Solução:** novo `tests/gui_interaction.py` (8 verificações, offscreen) com
  `QtTest.QTest`: login por teclado+clique (sucesso e falha), preenchimento do
  `DeviceDialog`, recarga de portas livres no `LinkDialog`, botões do diálogo
  de campos dinâmicos, seleção de linha nos Equipamentos e ativação do seletor
  de zona no separador Mapa.
- **Limite que fica:** fluxos modais (`exec()`) continuam fora do âmbito — em
  CI não há event loop bloqueante; cobri-los exigiria `QTimer` a fechar os
  diálogos ou refactor para fluxos não-modais.

### 2026-07-04 · #017 — Upload SharePoint limitado a 4 MB
- **Problema:** o PUT simples da Graph API rejeita ficheiros > 4 MB; o export
  CSV pode crescer além disso (e o executável, se vier a ser publicado,
  ultrapassa-o de certeza).
- **Solução:** implementado o *upload session* (`createUploadSession` + PUTs
  por chunks múltiplos de 320 KiB com `Content-Range`, conflictBehavior
  `replace`); o `upload()` escolhe automaticamente o caminho pelo tamanho.
- **Estado:** tal como o resto do conector, escrito mas por validar num tenant
  real (ver #008).

### 2026-07-04 · #018 — Builds não reprodutíveis (versões flutuantes)
- **Problema:** o `requirements.txt` usa gamas (`>=`); dois builds em datas
  diferentes podem apanhar versões distintas e comportar-se de forma diferente
  do que foi testado.
- **Solução:** criado `requirements.lock` com o conjunto exato de versões com
  que a 0.1.0 foi validada (smoke 35/35, GUI 12/12, QTest 8/8, selftest do
  bundle). O `requirements.txt` mantém as gamas para desenvolvimento; builds de
  release devem usar `pip install -r requirements.lock`. Ajustado o mínimo de
  `cryptography` para refletir a versão realmente validada (41.x).

### 2026-07-05 · #019 — Catálogo de VLANs sem partir bases existentes
- **Requisito:** CRUD de VLANs; até aqui a VLAN era texto livre em
  `Device.vlan`/`Port.vlan`, sem catálogo nem validação.
- **Problema:** transformar a VLAN numa FK exigiria alterar as tabelas
  `devices`/`ports` — o `create_all` do SQLAlchemy não adiciona colunas a
  tabelas existentes, e ainda não há migrações Alembic.
- **Solução:** tabela **aditiva** `vlans` (vlan_id único 1–4094, nome,
  descrição). Os campos texto mantêm-se; os formulários passam a dropdown
  editável alimentado pelo catálogo; a eliminação é bloqueada quando algum
  equipamento/porta usa `str(vlan_id)` (force limpa o campo, auditado). A
  migração para FK fica adiada para quando o Alembic entrar.

### 2026-07-05 · #020 — Registos de manutenção com datas
- **Requisito:** CRUD de manutenções com datas (realizadas e agendadas).
- **Solução:** tabela `maintenance_records` (device_id, `date`, `next_due`
  opcional, estado planned/done/cancelled, técnico, descrição), com cascade
  ORM — o histórico morre com o equipamento e **não** bloqueia a eliminação
  (ao contrário das portas ocupadas: histórico é registo, não dependência
  física). GUI: separador Manutenções com `QDateEdit` de calendário e
  agendamento da próxima intervenção. Export inclui `manutencoes.csv`.

### 2026-07-05 · #021 — Janelas CRUD dedicadas e exportação com data
- **Requisito:** janelas próprias para portas, ligações, VLANs, firewalls e
  manutenções, e janela de exportação com data.
- **Solução:** (1) `PortsDialog` por equipamento (botão "Portas…" em
  Equipamentos/Firewalls; porta com ligação não é eliminável aí — remove-se a
  ligação primeiro, mantendo a integridade estrita); (2) separador
  **Ligações** com listar/criar/editar estado (up/down refletido nas portas
  via `LinkRepository.set_status`)/eliminar (liberta as portas);
  (3) separador **Firewalls** — vista dedicada com categoria trancada no
  formulário, IP mascarado por perfil e contagem de portas WAN (`is_uplink`);
  (4) **ExportDialog** mostra a data/hora estampada na pasta
  `export_<timestamp>/` e filtra `manutencoes.csv` a partir de uma data.
  O `CrudTab` ganhou `buttons_layout` para os separadores acrescentarem
  botões próprios. Versão 0.2.0; testes 40/16/10 todos verdes.

### 2026-07-14 · #022 — Renomeação do pacote: `netmap` → `frimapper`
- **Contexto:** o pacote manteve o nome de trabalho `netmap` quando o produto
  passou a chamar-se Frimapper (#011), para desacoplar o nome comercial (com
  verificação de marca pendente) do identificador técnico.
- **Decisão:** alinhar os dois nomes agora, enquanto não há instalações em
  produção nem dependências externas do nome do pacote — mais tarde o custo
  só aumentaria.
- **Solução:** diretório e imports renomeados (`git mv` preserva o histórico);
  env vars `NETMAP_DATABASE_URL`/`NETMAP_SP_CLIENT_SECRET` renomeadas para
  `FRIMAPPER_DATABASE_URL`/`FRIMAPPER_SP_CLIENT_SECRET` (rutura limpa — não há
  ambientes configurados com as antigas); logger de auditoria e docs correntes
  atualizados. **As entradas históricas deste registo (#008, #011, #013)
  mantêm os caminhos `netmap/` da época — não se reescreve o histórico.**
- **Validação:** 40/16/10 verificações + selftest, e bundle PyInstaller
  reconstruído e validado. Versão 0.3.0.
- **Pendente (inalterado):** verificação formal de marca (EUIPO/INPI) e
  reserva de domínio/PyPI para "frimapper".

### 2026-07-14 · #023 — Build alternativo via auto-py-to-exe
- **Contexto:** a equipa dispõe do auto-py-to-exe (GUI do PyInstaller) na
  máquina Windows; a ferramenta não lê ficheiros `.spec`, pelo que o
  `frimapper.spec` não é diretamente reutilizável nela.
- **Solução:** config importável `tools/auto_py_to_exe.json` (Settings →
  Import Config) que replica o spec: onedir, console, `assets/icons`,
  hidden imports do passlib e `--collect-data/--collect-submodules diagrams`
  via *manual arguments*. O Graphviz empacota-se em *Additional Files*
  (`Graphviz\bin` → `graphviz/bin`), reconhecido pelo
  `runtime.configure_graphviz`. Instruções no README §7.
- **Validação:** o conjunto de flags equivalente foi construído e o binário
  passou o `--selftest` (o auto-py-to-exe gera exatamente este comando).
  O `frimapper.spec` mantém-se o caminho canónico de build (CI/scripts);
  o JSON é a via de conveniência para builds manuais na GUI.

### 2026-07-14 · #024 — Falha de arranque sem qualquer pista no Windows
- **Problema:** num build "Window Based" (sem consola), um erro no arranque
  faz a aplicação desaparecer sem mensagem; num "Console Based" lançado por
  duplo-clique, a consola fecha antes de se conseguir ler o traceback.
  Resultado reportado pelo utilizador: "o programa não executa".
- **Solução:** `main.py` instala um `sys.excepthook` que grava qualquer
  exceção fatal em `<dados>/crash.log` (com timestamp, em append) e, se o Qt
  já estiver de pé, mostra um QMessageBox com o erro e o caminho do log.
  README §8 ganhou as duas primeiras linhas de diagnóstico: correr o exe a
  partir de um terminal e consultar o `crash.log`; e o falso positivo
  SmartScreen/antivírus típico de executáveis PyInstaller não assinados.
- **Validação:** crash simulado escreve o traceback no `crash.log`; selftest
  continua OK.

### (modelo para a próxima entrada)
### AAAA-MM-DD · #00N — Título curto
- **Problema:** …
- **Impacto:** …
- **Solução:** …

## 5. Alojamento e Gestão Segura (SharePoint)

**Intenção:** usar o SharePoint para alojar o **programa** (distribuição para as
máquinas dos administradores) e os **backups CSV** (gestão segura com controlo
de acessos e versionamento do portal). O ambiente de desenvolvimento **não** tem
conector para o SharePoint — a integração corre na máquina do administrador.

**O que vive onde (recomendado):**

| Artefacto | Local | Notas |
|---|---|---|
| Código-fonte | Git (este repo) | Fonte de verdade do código; SharePoint não substitui Git. |
| Executável empacotado | SharePoint | Canal de distribuição/backup para admins. |
| Backups CSV | SharePoint | Versionados; credenciais já saem como `[protegido]`. |
| Documentação (`docs/`) | Git + cópia no SharePoint | Markdown canónico no repo. |
| `secret.key` (chave Fernet) | **FORA** do SharePoint | Cofre/gestor de segredos. Ver #008. |
| Base de dados `.db` | Local / partilha controlada | Se cifrada, a chave nunca no mesmo sítio. |

**Conector (opcional, desligado por defeito):** `frimapper/integrations/sharepoint.py`
usa Microsoft Graph (client credentials). Ativação em `config.ini`:

```ini
[sharepoint]
enabled   = true
tenant_id = <tenant-guid>
client_id = <app-guid>
site      = contoso.sharepoint.com:/sites/Redes
folder    = frimapper/backups
```

O `client_secret` vem da env var `FRIMAPPER_SP_CLIENT_SECRET` (nunca no ficheiro).
Requer app registada no Entra ID com permissão de aplicação
`Sites.ReadWrite.All` (consentimento de administrador) e as libs opcionais
`msal` + `requests`. Ficheiros > 4 MB precisam de *upload session* (TODO).

> **Pendente:** validar o conector numa máquina com acesso ao tenant e decidir se
> o executável também é publicado automaticamente ou só os CSV.

## 6. Próximos passos

- ~~Diálogos CRUD completos (Equipamentos, Zonas, Templates, Utilizadores).~~ ✅
- ~~Separador de gestão de utilizadores (criar contas, atribuir perfis) — Master.~~ ✅
- ~~Confirmação de force-delete com password de admin na GUI.~~ ✅
- ~~Biblioteca de ícones `Custom` (PLC, CCTV, régua, EV, solar, VoIP…).~~ ✅
- ~~Empacotamento PyInstaller + Graphviz~~ ✅ · migração de schema (Alembic)
  pendente — **prioridade subiu**: a VLAN-como-FK (#019) depende disto.
- Cobertura QTest de fluxos modais (force-delete de ponta a ponta na GUI).
- Validação do conector SharePoint (incl. upload session) num tenant real.
- Ícones definitivos (substituir os badges gerados).
