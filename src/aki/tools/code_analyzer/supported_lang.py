from enum import Enum

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_css
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript

from aki.tools.code_analyzer.parse_strategies.css_parse_strategy import (
    CssParseStrategy,
)
from aki.tools.code_analyzer.parse_strategies.default_parse_strategy import (
    DefaultParseStrategy,
)
from aki.tools.code_analyzer.parse_strategies.go_parse_strategy import (
    GoParseStrategy,
)
from aki.tools.code_analyzer.parse_strategies.parse_strategy import ParseStrategy
from aki.tools.code_analyzer.parse_strategies.python_parse_strategy import (
    PythonParseStrategy,
)
from aki.tools.code_analyzer.parse_strategies.typescript_parse_strategy import (
    TypeScriptParseStrategy,
)
from aki.tools.code_analyzer.tags_queries.c_sharp_tags_query import query_csharp
from aki.tools.code_analyzer.tags_queries.css_tags_query import query_css


class SupportedLang(Enum):
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    C = "c"
    CPP = "cpp"
    PYTHON = "python"
    RUST = "rust"
    GO = "go"
    C_SHARP = "c_sharp"
    RUBY = "ruby"
    JAVA = "java"
    PHP = "php"
    CSS = "css"
    TEXT = "text"

    @classmethod
    def get_query(cls, lang):
        """Retrieve the TAGS_QUERY for a given language."""
        # Now load your query string
        queries = {
            cls.JAVASCRIPT: tree_sitter_javascript.TAGS_QUERY,
            cls.TYPESCRIPT: tree_sitter_typescript.TAGS_QUERY,
            cls.C: tree_sitter_c.TAGS_QUERY,
            cls.CPP: tree_sitter_cpp.TAGS_QUERY,
            cls.PYTHON: tree_sitter_python.TAGS_QUERY,
            cls.RUST: tree_sitter_rust.TAGS_QUERY,
            cls.GO: tree_sitter_go.TAGS_QUERY,
            cls.C_SHARP: query_csharp,
            cls.RUBY: tree_sitter_ruby.TAGS_QUERY,
            cls.JAVA: tree_sitter_java.TAGS_QUERY,
            cls.PHP: tree_sitter_php.TAGS_QUERY,
            cls.CSS: query_css,
        }
        return queries.get(lang, None)

    @classmethod
    def get_language(cls, lang):
        """Retrieve the language parser for a given language."""
        languages = {
            cls.JAVASCRIPT: tree_sitter_javascript.language(),
            cls.TYPESCRIPT: tree_sitter_typescript.language_typescript(),
            cls.C: tree_sitter_c.language(),
            cls.CPP: tree_sitter_cpp.language(),
            cls.PYTHON: tree_sitter_python.language(),
            cls.RUST: tree_sitter_rust.language(),
            cls.GO: tree_sitter_go.language(),
            cls.C_SHARP: tree_sitter_c_sharp.language(),
            cls.RUBY: tree_sitter_ruby.language(),
            cls.JAVA: tree_sitter_java.language(),
            cls.PHP: tree_sitter_php.language_php(),
            cls.CSS: tree_sitter_css.language(),
        }
        return languages.get(lang, None)

    @classmethod
    def create_parse_strategy(cls, lang) -> ParseStrategy:
        """Returns the appropriate parsing strategy for the language."""
        strategies = {
            SupportedLang.TYPESCRIPT: TypeScriptParseStrategy(),
            SupportedLang.PYTHON: PythonParseStrategy(),
            SupportedLang.GO: GoParseStrategy(),
            SupportedLang.CSS: CssParseStrategy(),
        }
        return strategies.get(lang, DefaultParseStrategy())

    @classmethod
    def from_extension(cls, extension: str):
        return EXTENSION_TO_LANG.get(extension.lower())


EXTENSION_TO_LANG = {
    "cjs": SupportedLang.JAVASCRIPT,
    "mjs": SupportedLang.JAVASCRIPT,
    "mjsx": SupportedLang.JAVASCRIPT,
    "js": SupportedLang.JAVASCRIPT,
    "jsx": SupportedLang.JAVASCRIPT,
    "ctx": SupportedLang.TYPESCRIPT,
    "mts": SupportedLang.TYPESCRIPT,
    "mtsx": SupportedLang.TYPESCRIPT,
    "ts": SupportedLang.TYPESCRIPT,
    "tsx": SupportedLang.TYPESCRIPT,
    "h": SupportedLang.C,
    "c": SupportedLang.C,
    "hpp": SupportedLang.CPP,
    "cpp": SupportedLang.CPP,
    "py": SupportedLang.PYTHON,
    "rs": SupportedLang.RUST,
    "java": SupportedLang.JAVA,
    "go": SupportedLang.GO,
    "cs": SupportedLang.C_SHARP,
    "rb": SupportedLang.RUBY,
    "php": SupportedLang.PHP,
    "css": SupportedLang.CSS,
    "md": SupportedLang.TEXT,
    "sql": SupportedLang.TEXT,
    "json": SupportedLang.TEXT,
    "toml": SupportedLang.TEXT,
}
