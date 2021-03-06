# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio internationalization module."""

from __future__ import absolute_import, print_function

import os.path

from flask import current_app
from flask_babelex import Babel, lazy_gettext
from six import text_type

from .babel import MultidirDomain
from .jinja2 import filter_to_user_timezone, filter_to_utc
from .selectors import get_locale, get_timezone


def get_lazystring_encoder(app):
    """Custom JSONEncoder that handles lazy strings from Babel.

    Installed on Flask application by default by :py:class:`InvenioI18N`.
    """
    from speaklater import _LazyString

    class JSONEncoder(app.json_encoder):

        def default(self, o):
            if isinstance(o, _LazyString):
                return text_type(o)
            return super(JSONEncoder, self).default(o)

    return JSONEncoder


class InvenioI18N(object):
    """Invenio I18N extension.

    :param app: Flask application.
    :param data_formats: Override default date/time formatting.
    :param localeselector: Callback function used for locale selection.
        Defaults to using :py:func:`invenio_i18n.selectors.get_locale()`.
    :param timezoneselector: Callback function used for timezone selection.
        Defaults to ``BABEL_DEFAULT_TIMEZONE``.
    :param entrypoint: Entrypoint used to load translations from. Set to
        ``None`` to not load translations from entry points.
    """

    def __init__(self, app=None, date_formats=None, localeselector=None,
                 timezoneselector=None,
                 entrypoint='invenio_i18n.translations'):
        """Initialize extension."""
        self.babel = Babel(
            date_formats=date_formats,
            configure_jinja=True,
            default_domain=MultidirDomain())

        self.localeselector = localeselector
        self.timezoneselector = timezoneselector
        self.entrypoint = entrypoint
        self._locales_cache = None
        self._languages_cache = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Flask application initialization.

        The initialization will:

         * Set default values for the configuration variables.
         * Load translations from paths specified in
           ``I18N_TRANSLATIONS_PATHS``.
         * Load translations from ``app.root_path>/translations`` if it exists.
         * Load translations from a specified entry point.
         * Add ``toutc`` and ``tousertimezone`` template filters.
         * Install a custom JSON encoder on app.
        """
        app.config.setdefault("I18N_LANGUAGES", [])

        # Initialize Flask-BabelEx
        self.babel.init_app(app)
        self.babel.localeselector(self.localeselector or get_locale)
        self.babel.timezoneselector(self.timezoneselector or get_timezone)

        # Add paths to search for message catalogs
        domain = self.babel._default_domain
        # 1. Paths listed in I18N_TRANSLATIONS_PATHS
        for p in app.config.get("I18N_TRANSLATIONS_PATHS", []):
            domain.add_path(p)
        # 2. <app.root_path>/translations
        app_translations = os.path.join(app.root_path, 'translations')
        if os.path.exists(app_translations):
            domain.add_path(app_translations)
        # 3. Entrypoints
        if self.entrypoint:
            domain.add_entrypoint(self.entrypoint)

        # Register Jinja2 template filters for date formatting (Flask-Babel
        # already installs other filters).
        app.add_template_filter(filter_to_utc, name="toutc")
        app.add_template_filter(filter_to_user_timezone, name="tousertimezone")

        # Lazy string aware JSON encoder.
        app.json_encoder = get_lazystring_encoder(app)

        app.extensions['invenio-i18n'] = self

    def iter_languages(self):
        """Iterate over list of languages."""
        default_lang = self.babel.default_locale.language
        default_title = self.babel.default_locale.get_display_name(
            default_lang)

        yield (default_lang, lazy_gettext(default_title))

        for l, title in current_app.config.get('I18N_LANGUAGES', []):
            yield l, title

    def get_languages(self):
        """Get list of languages."""
        if self._languages_cache is None:
            self._languages_cache = list(self.iter_languages())
        return self._languages_cache

    def get_locales(self):
        """Get a list of supported locales.

        Computes the list using ``I18N_LANGUAGES`` configuration variable.
        """
        if self._locales_cache is None:
            langs = [self.babel.default_locale]
            for l, dummy_title in current_app.config.get('I18N_LANGUAGES', []):
                langs.append(self.babel.load_locale(l))
            self._locales_cache = langs
        return self._locales_cache
