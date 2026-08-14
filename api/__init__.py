def create_app():
    from .server import create_app as _create_app
    return _create_app()
