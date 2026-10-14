# Dashboards oficiais - Folha X

Portal com as três visões oficiais do time:

| Aba                | Arquivo                   | Gerador                 |
|--------------------|---------------------------|-------------------------|
| Abertas x Fechadas | `dashboard_periodo.html`  | `dashboard_periodo.py`  |
| Releases           | `dashboard_releases.html` | `dashboard_releases.py` |
| Acompanhamento     | `dashboard_folha_x.html`  | `dashboard_folha_x.py`  |

## Uso

1. Abra o `index.html` no navegador.
2. Clique no **⚙** de qualquer dashboard, cole seu PAT do Azure DevOps e clique em
   **Salvar no navegador** (o mesmo PAT vale para todos).
3. Clique em **Atualizar dados**.

Escopo do PAT: **Work Items → Read**. Para gravar comentários `#acompanhamento`
no dashboard de Releases, **Work Items → Read & Write**.

## Manutenção

Esta pasta é uma **cópia independente** dos arquivos da pasta principal
(`..\`): tem seus próprios geradores e seu próprio `ado_common.py`. Alterações
feitas lá não chegam aqui automaticamente, e vice-versa.

Para regerar os HTMLs desta pasta depois de alterar um gerador ou o
`ado_common.py` (rode de dentro desta pasta):

```powershell
python dashboard_periodo.py
python dashboard_releases.py
python dashboard_folha_x.py
```

Para incluir outra visão no portal, copie o gerador para cá, gere o HTML e
acrescente uma linha na lista `DASHBOARDS` no início do script do `index.html`.

Detalhes de cada dashboard (regras, campos usados, limitações) estão no
`README.md` da pasta principal.
