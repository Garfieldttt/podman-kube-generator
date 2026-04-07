from django.apps import AppConfig


class GeneratorConfig(AppConfig):
    name = 'generator'

    def ready(self):
        import generator.signals  # noqa: F401
