import sprockets.http

project = 'sprockets.http'
copyright = 'AWeber Communications, Inc.'
version = sprockets.http.__version__
release = '.'.join(str(v) for v in sprockets.http.version_info[0:2])

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode'
]

master_doc = 'index'
html_theme_options = {
    'github_user': 'sprockets',
    'github_repo': 'sprockets.http',
    'description': 'Tornado application runner',
    'github_banner': True,
}
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('http://docs.python.org/3/', None),
    'tornado': ('http://tornadoweb.org/en/latest/', None),
}
