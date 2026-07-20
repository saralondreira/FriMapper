# Frimapper

Gestor de inventário de infraestrutura de rede e gerador de topologias
(aplicação desktop, PySide6). A rede é mapeada **de raiz** e mantida numa base
de dados única (SQLite); os mapas PNG são gerados a partir dela
(diagrams + Graphviz).

| | |
|---|---|
| **Versão** | 0.3.0 |
| **Pacote Python** | `frimapper` |
| **Plataformas** | Windows / Linux |
| **Python** | 3.11+ |
| **Documentação** | [`docs/MANUAL.md`](docs/MANUAL.md) (referência técnica) · [`docs/DEVLOG.md`](docs/DEVLOG.md) (decisões e problemas/soluções) |

---

## 1. Pré-requisitos

- **Python 3.11 ou superior** (com `venv`).
- **Graphviz** (binário `dot`) — necessário apenas para o botão *Gerar Mapa*;
  a aplicação arranca e funciona sem ele.
  - Windows: <https://graphviz.org/download/> (ou empacotado no build, ver §6)
  - Debian/Ubuntu: `sudo apt install graphviz`
- Linux sem ambiente gráfico (CI/testes): libs Qt mínimas
  (`libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0`)
  e `QT_QPA_PLATFORM=offscreen`.

## 2. Instalação

```bash
git clone <url-do-repositório>
cd FriMapper

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt      # desenvolvimento (gamas de versões)
# ou, para reproduzir exatamente o conjunto validado:
pip install -r requirements.lock
```

## 3. Primeiro arranque

```bash
python main.py
```

No primeiro arranque a aplicação:

1. Cria a pasta de dados (ver §5) com a base de dados `network_inventory.db`,
   a chave de cifra `secret.key` e o log de auditoria `audit_network.log`;
2. Cria o utilizador administrador por defeito:

   | Utilizador | Password |
   |---|---|
   | `master` | `ChangeMe123!` |

> ⚠️ **Altere a password imediatamente** (separador *Utilizadores*) e crie as
> contas dos restantes perfis: **Técnico de Redes** (CRUD, mapas, export) e
> **Manutenção** (só leitura, com campos sensíveis mascarados).

Sequência típica de utilização inicial: criar **Localizações** → criar
**Templates** de equipamento (herdam as portas) → criar **VLANs** → adicionar
**Equipamentos** → criar **Ligações** (só portas livres) → **Gerar Mapa**.

## 4. Verificar a instalação

```bash
python main.py --selftest                                  # núcleo sem GUI
python tests/smoke_test.py                                 # 40 verificações
QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py        # 16 verificações
QT_QPA_PLATFORM=offscreen python tests/gui_interaction.py  # 10 verificações (QTest)
```

Para experimentar com dados de exemplo (cria BD própria e gera mapas, requer
Graphviz):

```bash
python tools/seed_demo.py demo
```

## 5. Onde ficam os dados

| Plataforma | Pasta de dados |
|---|---|
| Windows | `%APPDATA%\Frimapper` |
| Linux | `~/.frimapper` |
| Override | env var `FRIMAPPER_DATA` |

Conteúdo: `network_inventory.db` (BD), `secret.key` (chave Fernet),
`audit_network.log` (auditoria, rotativo), `maps/` (PNG gerados) e o
`config.ini` opcional.

**Backup:** copiar `network_inventory.db` **e** `secret.key` — guardados em
locais separados (sem a chave, os campos cifrados são irrecuperáveis; com a
chave junto da BD, a cifra não protege nada). Alternativa: *Exportar CSV* na
aplicação (credenciais saem como `[protegido]`).

## 6. Configuração opcional (`config.ini` na pasta de dados)

```ini
[database]
; migrar para servidor = mudar só esta linha (e instalar o driver)
url = sqlite:///C:/dados/network_inventory.db

[paths]
graphviz_dot_path = C:/Program Files/Graphviz/bin/dot.exe

[sharepoint]
enabled = false
```

Env vars: `FRIMAPPER_DATABASE_URL` (connection string),
`FRIMAPPER_DATA` (pasta de dados), `FRIMAPPER_SP_CLIENT_SECRET` (SharePoint).

## 7. Executável (sem Python instalado)

```bash
pip install -r requirements-build.txt
pyinstaller frimapper.spec
dist/Frimapper/frimapper --selftest    # validação do bundle
```

Windows: `tools\build_windows.ps1` (com `-GraphvizHome` para empacotar o
`dot` — o executável fica autónomo).

### Alternativa: auto-py-to-exe (interface gráfica)

O auto-py-to-exe usa o mesmo PyInstaller por baixo, mas não lê ficheiros
`.spec` — usa-se o config JSON incluído no repositório:

1. Abrir o auto-py-to-exe **a partir da raiz do projeto** (os caminhos do
   config são relativos): `cd FriMapper` → `auto-py-to-exe`;
2. **Settings → Configuration → Import Config From JSON File** →
   `tools/auto_py_to_exe.json` (preenche script, onedir, console, ícones e
   hidden imports do passlib + diagrams);
3. Para **empacotar o Graphviz** (opcional): em *Additional Files* →
   *Add Folder*, origem `C:\Program Files\Graphviz\bin`, destino
   `graphviz/bin` — o `runtime.configure_graphviz` encontra-o aí;
4. *Convert .py to .exe* e validar: `output\Frimapper\Frimapper.exe --selftest`.

Notas: manter **One Directory** (One File atrasa o arranque e não traz
vantagem — os dados vivem sempre em `%APPDATA%\Frimapper`); "Console Based"
mantém o output do `--selftest` visível — para distribuir aos utilizadores
finais pode mudar-se para "Window Based".

## 8. Problemas comuns no arranque

| Sintoma | Causa/ação |
|---|---|
| *"Graphviz ('dot') não encontrado"* ao gerar mapa | Instalar Graphviz ou definir `graphviz_dot_path` no `config.ini`; a restante aplicação funciona |
| Erro Qt `libEGL.so.1`/sem display (Linux) | Instalar as libs Qt do §1; em headless usar `QT_QPA_PLATFORM=offscreen` |
| Campos cifrados ilegíveis | A `secret.key` não corresponde à BD — repor a chave do backup |
| "O mapa da rede encontra-se desatualizado" (banner vermelho) | Normal após alterações — clicar *Gerar Mapa* |
| Banner laranja de equipamentos órfãos | Repor as ligações com o botão *Ligar…* |

---

Licenças de terceiros e detalhes de arquitetura, APIs internas, RBAC,
segurança e runbook completo: [`docs/MANUAL.md`](docs/MANUAL.md).
