# Frimapper — Manual Técnico e Referência do Projeto

> Referência **meticulosa e puramente técnica** de todo o projeto: arquitetura,
> modelo de dados, camadas, APIs internas, algoritmos, configuração, empacotamento,
> operação e testes. Sem dados de organização — apenas informação do projeto.

| | |
|---|---|
| **Produto** | Frimapper — Gestor de Inventário de Rede & Gerador de Topologias |
| **Pacote Python** | `netmap` |
| **Versão** | 0.1.0 |
| **Plataformas** | Windows / Linux (desktop) |
| **Ponto de entrada** | `main.py` |

---

## Índice

1. Sumário técnico
2. Glossário
3. Arquitetura (MVC em camadas)
4. Estrutura de ficheiros (anotada)
5. Enumerações de domínio
6. Modelo de dados (tabelas, campos, relações)
7. Regras de dependência e cascata
8. Segurança (mecanismos técnicos)
9. RBAC — perfis, permissões e masking
10. Camada de repositórios (API)
11. Camada de serviços (API)
12. Camada de controllers (API)
13. Camada de views (GUI)
14. Ciclo de vida do mapa (diagrams/Graphviz)
15. Pesquisa global
16. Campos dinâmicos
17. Deteção de órfãos
18. Exportação CSV
19. Integração SharePoint (opcional)
20. Configuração e caminhos
21. Instalação e execução
22. Empacotamento (PyInstaller)
23. Runbook operacional
24. Testes
25. Licenciamento de terceiros (NOTICE)
26. Decisões e etapas
27. Roadmap
28. Anexos

---

## 1. Sumário técnico

Aplicação **desktop** (PySide6) que substitui a gestão de inventário de rede em
folhas de cálculo por uma **base de dados única** (SQLite, migrável para servidor
corporativo via SQLAlchemy) e gera **mapas de topologia** (diagrams + Graphviz).

Princípios: **arquitetura MVC** desacoplada; **DB-agnóstico** acima da camada
`db/`; **security by design** (hashing argon2, cifra Fernet, auditoria, RBAC com
masking, ORM parametrizado); geração de mapa **diferida** e **thread-safe**.

---

## 2. Glossário

| Termo | Significado |
|---|---|
| Equipamento (Device) | Nó da rede (switch, firewall, servidor, PC, câmara, PLC…). |
| Modelo (Template) | Definição reutilizável; ao instanciar, herda as portas. |
| Porta (Port) | Interface de um equipamento; livre ou ocupada. |
| Ligação (Link) | Ligação entre duas portas. |
| Zona (Location) | Área física hierárquica (pavilhão → bastidor → sala). |
| Campo dinâmico | Par chave-valor livre por equipamento (`DeviceAttribute`). |
| Órfão | Equipamento sem ligação após eliminação em cascata. |
| Staleness | Mapa desatualizado face a alterações na BD. |
| DTO | Objeto de transferência plano entre View e Controller. |

---

## 3. Arquitetura (MVC em camadas)

```
VIEW        gui/views/*  +  gui/models/* (Qt)   ── só conhece DTOs
   │  DTOs (gui/dto.py)
CONTROLLER  gui/controllers/*                    ── gere sessões, orquestra
   │
MODEL       services/  ·  repositories/  ·  db/  ·  security/  ·  domain/
```

Invariantes:
- As **Views não importam ORM** nem abrem sessões de BD.
- Os **Controllers** abrem/fecham sessões e devolvem **DTOs**.
- Apenas `db/` conhece o **motor concreto** (SQLite/Postgres/…).
- Os **Repositories** são a única via de escrita (com auditoria e dependências).

---

## 4. Estrutura de ficheiros (anotada)

```
netmap/
├── __init__.py           APP_NAME = "Frimapper", __version__
├── config.py             AppConfig.load(): connection string + caminhos + [sharepoint]
├── paths.py              resource_dir()/data_dir() (empacotamento)
├── runtime.py            configure_graphviz(): dot no PATH
├── domain/enums.py       Role, DeviceCategory, PortStatus, LinkType, DeviceStatus
├── db/
│   ├── base.py           Database (engine, sessionmaker, PRAGMA FK), Base declarativa
│   ├── types.py          EncryptedString (TypeDecorator Fernet)
│   └── models.py         User, Location, DeviceTemplate, Device, Port, Link,
│                         DeviceAttribute, SystemMeta
├── security/
│   ├── auth.py           hash_password/verify_password/needs_rehash (passlib argon2)
│   ├── crypto.py         FieldCipher (Fernet; chave em ficheiro 0600)
│   ├── audit.py          AuditLogger (RotatingFileHandler)
│   └── rbac.py           Permission, ROLE_PERMISSIONS, masking
├── repositories/
│   ├── base.py           BaseRepository, DependencyError
│   ├── meta.py           get_meta/set_meta (SystemMeta)
│   └── repositories.py   User/Location/Template/Device/Port/Link repos
├── services/
│   ├── bootstrap.py      initialize_app, ensure_master_user, AppContext
│   ├── integrity_service.py  deteção de órfãos
│   ├── synthesis_service.py  síntese por nó
│   ├── map_service.py    geração do mapa + staleness
│   ├── search_service.py pesquisa global
│   ├── export_service.py export CSV
│   └── user_service.py   gestão de contas + verify_admin
└── gui/
    ├── dto.py            DeviceRow/Form, Option, Location*, Template*, User*, PortView…
    ├── session.py        UserSession (user_id, username, role)
    ├── controllers/      auth, device, link, location, template, user, map, search, export
    ├── models/device_table_model.py  QAbstractTableModel (masking + destaque órfão)
    └── views/            login_view, main_window, dialogs, tabs, node_synthesis_view
assets/icons/*.png        12 ícones Custom (badges)
tools/                    make_icons.py · seed_demo.py · build_windows.ps1
tests/                    smoke_test.py · gui_smoke.py · gui_interaction.py
main.py                   entrypoint (+ --selftest)   ·   frimapper.spec
```

---

## 5. Enumerações de domínio (`domain/enums.py`)

- **Role:** `MASTER`, `TECH`, `MAINTENANCE`.
- **DeviceCategory** (22): `internet, router, firewall, switch, regua, servidor,
  ups, nas, computador, portatil, telefone_fixo, telefone, impressora, ap,
  cabo_vazio, camaras, cctv, controlo_acessos, automatos, solar, carregador_ev,
  voip`. Propriedade `is_passive` → `True` para `regua` e `cabo_vazio`.
- **PortStatus:** `up`, `down`, `unused`.
- **LinkType:** `active`, `passive`.
- **DeviceStatus:** `active`, `inactive`, `unknown`.

---

## 6. Modelo de dados

Motor: SQLAlchemy 2.0 (estilo `Mapped`). Timestamps `created_at`/`updated_at` em
quase todas as tabelas. FK reforçadas no SQLite (`PRAGMA foreign_keys=ON`).

**users** — `id`, `username`⧉, `password_hash`, `full_name`, `role`, `is_active`,
`last_login`.
**locations** — `id`, `name`⧉, `description`, `parent_id`→locations (hierarquia).
**device_templates** — `id`, `name`⧉, `manufacturer`, `model`, `category`,
`port_count`, `port_speeds`, `port_prefix`, `is_passive`.
**devices** — `id`, `hostname`⧉, `category`, `template_id`→templates,
`location_id`→locations, `status`, `needs_relink`, `ip_mgmt`, `mac`, `vlan`,
`os_detected`, `assigned_user`, `serial_number`, `notes`, `snmp_community`🔒,
`access_password`🔒.
**ports** — `id`, `device_id`→devices, `name`, `speed`, `status`, `vlan`,
`is_uplink`; único (`device_id`,`name`).
**links** — `id`, `port_a_id`→ports, `port_b_id`→ports, `link_type`, `status`,
`notes`.
**device_attributes** — `id`, `device_id`→devices, `name`, `value`; único
(`device_id`,`name`).
**system_meta** — `key`(PK), `value`. Chaves usadas: `db_last_modified`,
`map_last_generated`, `map_last_path`.

Legenda: ⧉ único · 🔒 cifrado em repouso (Fernet).

Relações com cascata ORM: `Device.ports`, `Device.attributes` →
`cascade="all, delete-orphan"` (usadas apenas no force-delete).

---

## 7. Regras de dependência e cascata

Definidas em cada repositório (`dependencies()` + `_cascade()`), aplicadas por
`BaseRepository.delete(obj, force)`:

| Entidade | Bloqueio (dependencies) | Cascata (force) |
|---|---|---|
| Location | equipamentos na zona; sub-zonas | apaga equipamentos e sub-zonas |
| DeviceTemplate | equipamentos que usam o modelo | desassocia (`template_id=None`) |
| Device | portas ocupadas (com link) | remove links; ports caem por ORM |
| Port | tem link | remove o link |
| User | é o único Master ativo | — (nunca permitido) |

Sem `force`, `delete()` levanta **`DependencyError`** com a lista de dependências.
Com `force`, corre `_cascade()` e regista **`FORCE_DELETE`** na auditoria. O
`force=True` só é passado após validação de **password de Master** na GUI.

---

## 8. Segurança (mecanismos técnicos)

- **Passwords:** `passlib` `CryptContext(schemes=["argon2","bcrypt"])`;
  `hash_password`, `verify_password`, `needs_rehash` (rehash transparente no login).
- **Cifra em repouso:** `FieldCipher` (Fernet). Chave carregada/criada em
  `secret.key` com permissões `0600`. `EncryptedString` (TypeDecorator) cifra/
  decifra transparentemente `snmp_community` e `access_password`. A cifra é
  injetada no bootstrap **antes** de qualquer acesso a essas colunas.
- **Auditoria:** `AuditLogger` → `audit_network.log` (RotatingFileHandler, 5 MB ×
  10). Formato: `data | host=<máquina> | user=<u> | action=<A> | entity=<E> |
  id=<id> | <detalhe>`. Ações: CREATE, UPDATE, DELETE, FORCE_DELETE, LOGIN_OK,
  LOGIN_FAIL, BOOTSTRAP.
- **Anti SQL-injection:** exclusivamente ORM/consultas parametrizadas.
- **Chave (crítico):** `secret.key` deve viver separada da BD cifrada.

---

## 9. RBAC — perfis, permissões e masking (`security/rbac.py`)

**Permission:** `VIEW, CREATE, EDIT, DELETE, FORCE_DELETE, MANAGE_USERS,
GENERATE_MAP, EXPORT`.

**ROLE_PERMISSIONS:**
- `MASTER` → todas.
- `TECH` → `VIEW, CREATE, EDIT, DELETE, GENERATE_MAP, EXPORT`.
- `MAINTENANCE` → `VIEW`.

**Masking (`SENSITIVE_FIELDS`):** `ip_mgmt, mac, vlan, os_detected,
snmp_community, access_password, serial_number` → apresentados como `***` para o
perfil `MAINTENANCE`. `is_field_masked(role, field)` decide; aplicado em
`DeviceTableModel` e no painel de síntese (VLAN). O editor de campos dinâmicos
está atrás de `EDIT` (Manutenção não acede).

---

## 10. Camada de repositórios (API)

**`BaseRepository`** (`repositories/base.py`)
- `get(id)`, `list(**filters)`, `add(obj)`, `update(obj, **fields)`,
  `delete(obj, force=False)`.
- Extensão: `dependencies(obj) -> list[str]`, `_cascade(obj)`.
- Internos: `_touch_db()` (atualiza `db_last_modified`), `_audit(action, obj)`.
- **Unit of Work:** os repos fazem `flush`; o **commit** é do controller/serviço.
- `DependencyError(message, dependencies)`.

**Concretos** (`repositories/repositories.py`)
- `UserRepository`: `by_username`, `dependencies` (protege o único Master).
- `LocationRepository`: `dependencies`, `_cascade` (apaga equipamentos/sub-zonas).
- `TemplateRepository`: `dependencies`, `_cascade` (desassocia devices).
- `DeviceRepository`: `by_hostname`, `create_from_template`, `add_manual_port`,
  `occupied_ports`, `free_ports`, `attributes`, `set_attributes`, `dependencies`,
  `_cascade`.
- `PortRepository`: `dependencies`, `_cascade`.
- `LinkRepository`: `create(port_a, port_b, **kw)` — valida portas livres, define
  o estado das portas e **limpa `needs_relink`** de ambos os equipamentos.

---

## 11. Camada de serviços (API)

- **bootstrap** — `initialize_app(config) -> AppContext(config, db, cipher,
  audit)` (configura Graphviz, cifra, BD, auditoria); `ensure_master_user(...)`.
- **integrity_service** — `device_ids_in_location(id)`, `link_peers(ids)`,
  `has_no_links(id)`, `mark_orphans(ids) -> list[str]`, `orphan_hostnames()`.
- **synthesis_service** — `for_device(device) -> NodeSynthesis` (com
  `PortSynthesis`: porta, velocidade, estado, VLAN, ligado-a, utilizador).
- **map_service** — `is_stale()`, `last_map_path()`, `generate(view, location_id)`;
  `ICON_FILES`, `NATIVE_FALLBACK`, `_edge_style`, `_devices_for_view`.
- **search_service** — `search(term) -> list[SearchResult]`.
- **export_service** — `export_all(dir) -> list[str]` (6 CSV).
- **user_service** — `list_users`, `create_user`, `set_password`, `set_role`,
  `set_active`, `delete_user`, `verify_admin`.

---

## 12. Camada de controllers (API)

Cada controller recebe `(ctx, session)` (exceto Auth/Map/Search/Export que só
precisam de `ctx`) e devolve **DTOs**.

- **AuthController** — `login(u,p) -> UserSession|None`, `verify_admin(u,p) -> bool`.
- **DeviceController** — `list_devices()->[DeviceRow]`, `orphan_hostnames()`,
  `template_options()`, `location_options()`, `get_form(id)->DeviceForm`,
  `create(form)`, `update(id,form)`, `delete(id,force)->[str]`,
  `get_attributes(id)->[(str,str)]`, `save_attributes(id,pairs)`,
  `synthesis(id)->SynthesisView`.
- **LinkController** — `form_data()->([Option],{id:[Option]})`,
  `create(a,b,down)`.
- **LocationController** — `list_rows`, `options(exclude_id)`, `get_form`,
  `create`, `update`, `delete(id,force)->[str]`.
- **TemplateController / UserController** — `list_rows`, `get_form`, `create`,
  `update`, `delete`.
- **MapController** — `is_stale`, `last_path`, `generate(view)`.
- **SearchController** — `search(term)->[SearchHit]`.
- **ExportController** — `export_csv()->[str]`, `sharepoint_enabled()`,
  `upload_to_sharepoint(files)`.

---

## 13. Camada de views (GUI)

- **LoginView** — autenticação (AuthController).
- **MainWindow** — barra de pesquisa; banners de **staleness** (vermelho) e
  **órfãos** (laranja); separadores: Equipamentos, Localizações, Templates, Mapa,
  Utilizadores (só Master). Botões dos Equipamentos: Adicionar, Editar, Eliminar,
  **Ligar…**, **Campos…**, Exportar CSV. Duplo-clique → síntese.
- **Diálogos** (`dialogs.py`) — `DeviceDialog`, `LocationDialog`, `TemplateDialog`,
  `UserDialog`, `LinkDialog` (só portas livres), `DeviceAttributesDialog`,
  `AdminPasswordDialog`, `confirm_force_delete()`.
- **CrudTab** (`tabs.py`) — base genérica (tabela + Novo/Editar/Eliminar, RBAC,
  fluxo de force-delete + alerta de órfãos, callback `on_change`).
- **DeviceTableModel** — masking por sessão + fundo laranja nas linhas órfãs.
- **NodeSynthesisView** — tabela de portas com estado a cores.

---

## 14. Ciclo de vida do mapa (`services/map_service.py`)

1. **Diferido:** só corre em `generate()` (clique em "Gerar Mapa"), num
   **worker thread** (o contexto da `diagrams` é **thread-local**; todo o
   `with Diagram()` corre na mesma thread).
2. Abre `with Diagram(filename=..., show=False, outformat="png",
   graph_attr={fontsize, splines, rankdir})`.
3. Agrupa equipamentos por localização em `Cluster` ("Sem localização" para nulos).
4. `node_for(device)`: **(1)** ícone Custom `assets/icons/<categoria>.png` por
   **caminho absoluto**; **(2)** ícone nativo (`NATIVE_FALLBACK`); **(3)** `Blank`.
5. Arestas dos links; `status == down` → `color="red", style="dashed", label="down"`.
6. Ao **sair do contexto**, o Graphviz compila o PNG (nome com timestamp; título
   com data/hora no canvas).
7. Grava `map_last_generated`/`map_last_path`; **staleness** = `db_last_modified >
   map_last_generated` (comparação lexicográfica de ISO-8601).

Vistas: `full` (tudo), `core` (internet/router/firewall/switch/servidor/nas),
`location` (uma zona).

---

## 15. Pesquisa global (`services/search_service.py`)

`search(term)` faz `ILIKE %term%` em `hostname, mac, ip_mgmt, assigned_user,
vlan, serial_number` **e** nos valores de `device_attributes`. Para cada
resultado resolve o **switch/porta** onde o equipamento está ligado (via links).
Tudo parametrizado (sem injeção).

---

## 16. Campos dinâmicos (EAV)

`DeviceAttribute(device_id, name, value)`, único por (device, name).
`DeviceRepository.set_attributes(device, pairs)` **sincroniza** (adiciona novos,
atualiza existentes, remove ausentes; nomes vazios ignorados) com auditoria. Um
switch pode ter campos diferentes de outro; num PC guardam-se detentor, conta
logada, IPs/MACs extra, CPU/RAM, etc. Entram na **pesquisa** e no **export**.

---

## 17. Deteção de órfãos (`services/integrity_service.py`)

Fluxo num force-delete: **antes** — `link_peers(deletion_ids)` recolhe os
equipamentos externos ligados ao conjunto a eliminar; **depois** —
`mark_orphans(peers)` marca `needs_relink=True` nos que ficaram sem qualquer
link e devolve os hostnames. Para zonas, `deletion_ids =
device_ids_in_location(id)` (recursivo). Criar uma nova ligação limpa o flag
(`LinkRepository.create`). GUI: popup + banner laranja + linhas destacadas.

---

## 18. Exportação CSV (`services/export_service.py`)

`export_all(dir)` cria a pasta `export_<timestamp>/` com 6 ficheiros:
`localizacoes.csv`, `templates.csv`, `equipamentos.csv`, `portas.csv`,
`ligacoes.csv`, `campos_dinamicos.csv`. Codificação `utf-8-sig` (Excel).
**Campos cifrados nunca saem em claro** → `[protegido]`.

---

## 19. Integração SharePoint (opcional)

`integrations/sharepoint.py` (Microsoft Graph, client-credentials). Desligado por
defeito. `client_secret` via env `NETMAP_SP_CLIENT_SECRET`. Requer app no Entra
ID com `Sites.ReadWrite.All`; libs opcionais `msal`+`requests`. Ficheiros > 4 MB
usam **upload session** (chunks múltiplos de 320 KiB — por validar em tenant
real). Import tardio — não é dependência de runtime.

---

## 20. Configuração e caminhos

**`config.ini`** — `[database] url/echo`, `[paths]
audit_log/secret_key/map_output/icon_dir/graphviz_dot_path`, `[sharepoint]
enabled/tenant_id/client_id/site/folder`.

**Env vars:** `NETMAP_DATABASE_URL` (connection string),
`NETMAP_SP_CLIENT_SECRET` (segredo SharePoint), `FRIMAPPER_DATA` (dir de dados).

**Caminhos (`paths.py`):** recursos read-only em `resource_dir()`
(`sys._MEIPASS` quando empacotado); dados graváveis em `data_dir()`
(`%APPDATA%\Frimapper` / `~/.frimapper`, ou `FRIMAPPER_DATA`). Ficheiros:
`network_inventory.db`, `secret.key`, `audit_network.log`, `maps/`.

**Migração de BD:** mudar apenas `[database] url` (e instalar o driver:
`psycopg`/`PyMySQL`/`pyodbc`).

---

## 21. Instalação e execução

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # dev (gamas) · release: -r requirements.lock
python main.py
python main.py --selftest                               # valida núcleo sem GUI
python tests/smoke_test.py                              # 35 verificações
QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py     # 12 verificações
QT_QPA_PLATFORM=offscreen python tests/gui_interaction.py  # 8 verificações (QTest)
python tools/seed_demo.py demo                          # dados + mapas (requer Graphviz)
```

Primeiro arranque cria `master` / `ChangeMe123!` (alterar).

---

## 22. Empacotamento (PyInstaller)

`frimapper.spec` (onedir). `datas`: `assets/icons` + dados da `diagrams`.
`GRAPHVIZ_HOME` (build) → empacota `graphviz/bin`, colocado no PATH por
`runtime.configure_graphviz`. `hiddenimports`: handlers passlib + submódulos
`diagrams`.

```bash
pip install -r requirements-build.txt
pyinstaller frimapper.spec
dist/Frimapper/frimapper --selftest
```

Windows: `tools/build_windows.ps1`.

---

## 23. Runbook operacional

- **Backup:** copiar `network_inventory.db` **e** `secret.key` (em locais
  separados); ou Exportar CSV. **Restauro:** repor `.db` + a chave correspondente.
- **Logs:** `audit_network.log` roda automaticamente; arquivar conforme política.
- **Utilizadores:** separador Utilizadores (Master).
- **Sintomas → ação:** mapa desatualizado → Gerar Mapa · órfãos → Ligar… · falha
  Graphviz → instalar/empacotar `dot` · campos ilegíveis → repor a `secret.key`.

---

## 24. Testes

- **`tests/smoke_test.py`** (35): bootstrap, hashing, cifra em repouso, herança
  de portas, ocupação, dependências/force-delete, órfãos, campos dinâmicos,
  pesquisa, export (não-vazamento), utilizadores/verify_admin, staleness.
- **`tests/gui_smoke.py`** (12, offscreen): construção de janela/diálogos para os
  3 perfis, RBAC, masking, síntese, ligações, campos dinâmicos.
- **`tests/gui_interaction.py`** (8, offscreen, `QtTest`): cliques e teclado
  simulados — login (sucesso/falha), formulário de equipamento, recarga de
  portas livres, botões dos campos dinâmicos, seleção de linhas, seletor de
  vista do mapa.
- **`main.py --selftest`**: valida o bundle empacotado.
- **Limitação:** fluxos **modais** (`exec()`) não são exercitados em CI (sem
  event loop bloqueante) — cobri-los exigiria fecho temporizado por `QTimer`.

---

## 25. Licenciamento de terceiros (NOTICE)

Todas permitem uso interno sem restrições de distribuição:

| Componente | Licença | Fase |
|---|---|---|
| PySide6 | LGPL v3 (ligação dinâmica) | runtime |
| SQLAlchemy | MIT | runtime |
| passlib | BSD | runtime |
| argon2-cffi | MIT | runtime |
| bcrypt | Apache-2.0 | runtime |
| cryptography | Apache-2.0 / BSD | runtime |
| diagrams | MIT | runtime |
| Graphviz (`dot`) | EPL/CPL | sistema |
| PyInstaller | GPL c/ exceção de runtime | build |
| Pillow | HPND (permissiva) | build |

---

## 26. Decisões e etapas

Cronologia detalhada de decisões e de **problemas/soluções** em
[`DEVLOG.md`](DEVLOG.md). Decisões estruturais: sem importação de Excels; SQLite +
SQLAlchemy (DB-agnóstico); integridade estrita + force-delete auditado; segurança
by design; PySide6 + MVC; diagrams + Graphviz (geração diferida); PyInstaller
(separação recursos/dados); alerta de órfãos; campos dinâmicos.

---

## 27. Roadmap

~~Testes `QTest`~~ ✅ (#016) · ~~lock de versões~~ ✅ (`requirements.lock`, #018)
· ~~upload session (>4 MB)~~ ✅ (#017, por validar em tenant) · migração de
schema (Alembic) · ícones definitivos · validação do conector SharePoint ·
cobertura QTest de fluxos modais.

---

## 28. Anexos

**Comandos**

```bash
python main.py                 python main.py --selftest
python tools/make_icons.py assets/icons
python tools/seed_demo.py demo
python tests/smoke_test.py
QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py
QT_QPA_PLATFORM=offscreen python tests/gui_interaction.py
pyinstaller frimapper.spec
```

**Caminhos por defeito** — dados: `%APPDATA%\Frimapper` / `~/.frimapper` /
`FRIMAPPER_DATA`; ficheiros: `network_inventory.db`, `secret.key`,
`audit_network.log`, `maps/`.

**Utilizador inicial** — `master` / `ChangeMe123!` (alterar).

---

_Manter sincronizado com `docs/DEVLOG.md` a cada evolução._
