# A13-01 — контрактный регресс RM-* (без LLM)

**Verdict: `pass` (слой R0).** HEAD `f38fd17`. Pytest зелёный: **160 passed, 1 skipped, exit 0**. Skip — `test_optional_pbt_skips_without_local_runner` (нет Hypothesis): **pass плана**, не fail. LLM / `:1240` не вызывались.

| Проверка | Наблюдение | Evidence |
|---|---|---|
| Pytest unit/integration/e2e/evals | 161 collected; 160 pass; 1 skip; exit 0 | [pytest-1.txt](pytest-1.txt) |
| PowerShell smoke + layout | 4/4, exit 0 | [smoke-ps-1.txt](smoke-ps-1.txt) |
| Bash smoke, Windows working tree | exit 127, `bash\r` (index LF, worktree CRLF, system `core.autocrlf=true`) | [smoke-sh-working-tree-1.txt](smoke-sh-working-tree-1.txt) |
| Bash smoke, `git archive` LF | 4/4, exit 0; shebang без CR | [smoke-sh-archive-1.txt](smoke-sh-archive-1.txt) |

Рабочая гипотеза (гейты T1–T8 / F-010 / F-009 / F-006 / P2 на диске) подтверждена pytest. Альтернатива «красный контракт» не сработала. R0 **не** доказывает, что ornith напишет live spec.

Якоря RM из [regression-plan.md](../../regression-plan.md) присутствуют в зелёном прогоне (`tests/unit/test_fsm.py`, `test_context.py`, `test_integrity.py` / `test_fsm_mutations.py`, `test_spec_style.py`). `.gitattributes` задаёт `*.sh eol=lf`; канонические blob’ы LF.

Ограничение: прямой WSL-запуск из Windows-checkout всё ещё ломается CRLF (тот же класс, что [F-001](../../../findings/F-001.md)). Новый RM не открывался. `git config` не менялся.

## Handoff

- R0 pytest + PS smoke зелёные → **можно стартовать [A13-02](../../packets/A13-02.md)** при живом `:1240` (иначе `blocked`, без облака / Studio `:1234`).
- Skills с текущей ветки; без A09 extras «только SLICE-01»; полный A09 11/11 не гонять до закрытия R1.
- R1 доказывает SUT, не этот гейт на диске.
