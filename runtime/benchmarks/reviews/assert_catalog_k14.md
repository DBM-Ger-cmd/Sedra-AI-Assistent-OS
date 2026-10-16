Review of `assert_catalog.py`, function `_gen_k14` (kind K14, form). Everything else in the file passes its tests; change ONLY this function.

1. The generated test does not check "all imports at the start of the module". The task says: nothing but imports before the LAST import of the module body. A source that has `VALUE = 1` and AFTER it `import json` must make the generated test fail. Add these generated lines (write them with the same style as the lines around them) after the docstring check:

    last = max((i for i, node in enumerate(tree.body) if isinstance(node, (ast.Import, ast.ImportFrom))), default=-1)
    assert all(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body[:last + 1])

2. The generated test must NOT import the module under test. Remove the generated lines `mod = importlib.import_module(module)` and the `importlib` imports; read the source file only: its path is the module name with dots turned into "/" and ".py" at the end (for example "pkg.mod" -> "pkg/mod.py"), read as UTF-8 text with `pathlib.Path(...).read_text(encoding='utf-8')`. The test is run in a folder that holds that file and the module must never be executed.

3. Keep the other checks of K14 (comment, docstring of module, classes and functions, imports nested in functions or classes, every imported name used as a name). The mutant "import re, then VALUE = 1, then import json, a function that uses both" must make the generated test fail; the good example (imports at the top, both used, no comment, no docstring) must pass.
