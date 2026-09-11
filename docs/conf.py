import sprockets.http

project = 'sprockets.http'
copyright = 'AWeber Communications, Inc.'
version = sprockets.http.__version__
release = '.'.join(str(v) for v in sprockets.http.version_info[0:2])

extensions = []
html_theme = 'python_docs_theme'
html_static_path = ['.']
html_css_files = ['custom.css']

# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
extensions.append('sphinx.ext.autodoc')

# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
extensions.append('sphinx.ext.intersphinx')
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'tornado': ('https://www.tornadoweb.org/en/latest/', None),
}

# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html
extensions.append('sphinx.ext.extlinks')
extlinks = {
    'compare':
    ("https://github.com/sprockets/sprockets.http/compare/%s", "%s"),
    'issue': ("https://github.com/sprockets/sprockets.http/issues/%s", "#%s"),
}
