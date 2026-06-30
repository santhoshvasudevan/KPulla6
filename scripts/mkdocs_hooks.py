"""MkDocs hooks — debounce live reload to reduce rebuild loops from editor auto-save."""


def on_serve(server, config, builder):
    server.build_delay = 2.0
