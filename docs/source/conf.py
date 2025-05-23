import os
import sys

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Telegram Reader'
copyright = '2025, Daniel Castro'
author = 'Daniel Castro'
release = '1.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # para docstrings estilo Google
    'sphinx_autodoc_typehints'
]

templates_path = ['_templates']
exclude_patterns = []

language = 'pt_BR'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
#html_theme = 'sphinx_rtd_theme'
sys.path.insert(0, os.path.abspath('../../'))  # garante acesso ao código em C:\Varios\TelegramReader
