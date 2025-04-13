import logging
import os
from typing import Dict, Optional

import tree_sitter

from .parse_strategies.parse_strategy import ParseStrategy
from .supported_lang import SupportedLang


class LanguageResources:
    def __init__(
        self,
        parser: tree_sitter.Parser,
        query: tree_sitter.Query,
        strategy: ParseStrategy,
    ):
        self.parser = parser
        self.query = query
        self.strategy = strategy


class LanguageParser:
    def __init__(self):
        self.loaded_resources: Dict[SupportedLang, LanguageResources] = {}
        self.initialized = False

    async def prepare_lang(self, name: SupportedLang) -> LanguageResources:
        try:
            lan = tree_sitter.Language(SupportedLang.get_language(name))
            parser = tree_sitter.Parser(lan)
            query = lan.query(SupportedLang.get_query(name))
            strategy = SupportedLang.create_parse_strategy(name)

            resources = LanguageResources(
                parser=parser,
                query=query,
                strategy=strategy,
            )

            self.loaded_resources[name] = resources
            return resources
        except Exception as error:
            logging.error(f"Error parsing file: {error}")

    async def get_resources(self, name: SupportedLang) -> LanguageResources:
        resources = self.loaded_resources.get(name)
        if not resources:
            return await self.prepare_lang(name)
        return resources

    async def get_parser_for_lang(self, name: SupportedLang) -> tree_sitter.Parser:
        resources = await self.get_resources(name)
        return resources.parser

    async def get_query_for_lang(self, name: SupportedLang) -> tree_sitter.Query:
        resources = await self.get_resources(name)
        return resources.query

    async def get_strategy_for_lang(self, name: SupportedLang) -> ParseStrategy:
        resources = await self.get_resources(name)
        return resources.strategy

    @staticmethod
    def get_file_extension(file_path: str) -> str:
        return os.path.splitext(file_path)[1].lower()[1:]

    def guess_the_lang(self, file_path: str) -> Optional[SupportedLang]:
        ext = self.get_file_extension(file_path)
        return SupportedLang.from_extension(ext)
