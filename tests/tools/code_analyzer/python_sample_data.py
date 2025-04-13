"""Python sample data for code analyzer tests."""

PYTHON_SAMPLE = {
    "sample_module.py": '''
        @decorator
        class SampleClass:
            """Class docstring."""
            
            def __init__(self, param: str):
                self.param = param
            
            @staticmethod
            def static_method() -> None:
                """Static method docstring."""
                pass
            
            @property
            def prop(self) -> str:
                return self.param
        
            def sample_function(a: int, b: int = 10) -> int:
                """Function docstring."""
                return a + b

        TypeAlias = str
        ''',
    "package/__init__.py": """
        # Package initialization
        from .module import example_func
        """,
    "package/module.py": """
        def example_func():
            return "Hello World"
        
        class ExampleClass:
            pass
        """,
}
