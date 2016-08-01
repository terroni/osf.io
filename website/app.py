# -*- coding: utf-8 -*-

import importlib
import json
import os
from collections import OrderedDict

import django
from werkzeug.contrib.fixers import ProxyFix

import framework
import website.models
from framework.addons.utils import render_addon_capabilities
from framework.flask import app, add_handlers
from framework.logging import logger
from framework.mongo import handlers as mongo_handlers
from framework.mongo import set_up_storage
from framework.postcommit_tasks import handlers as postcommit_handlers
from framework.sentry import sentry
from framework.celery_tasks import handlers as celery_task_handlers
from framework.transactions import handlers as transaction_handlers
from modularodm import storage
from website.addons.base import init_addon
from website.project.licenses import ensure_licenses
from website.project.model import ensure_schemas
from website.project.taxonomies import ensure_taxonomies
from website.routes import make_url_map
from website import maintenance

# This import is necessary to set up the archiver signal listeners
from website.archiver import listeners  # noqa
from website.mails import listeners  # noqa
from website.notifications import listeners  # noqa
from api.caching import listeners  # noqa


def init_addons(settings, routes=True):
    """Initialize each addon in settings.ADDONS_REQUESTED.

    :param module settings: The settings module.
    :param bool routes: Add each addon's routing rules to the URL map.
    """
    settings.ADDONS_AVAILABLE = getattr(settings, 'ADDONS_AVAILABLE', [])
    settings.ADDONS_AVAILABLE_DICT = getattr(settings, 'ADDONS_AVAILABLE_DICT', OrderedDict())
    for addon_name in settings.ADDONS_REQUESTED:
        addon = init_addon(app, addon_name, routes=routes)
        if addon:
            if addon not in settings.ADDONS_AVAILABLE:
                settings.ADDONS_AVAILABLE.append(addon)
            settings.ADDONS_AVAILABLE_DICT[addon.short_name] = addon
    settings.ADDON_CAPABILITIES = render_addon_capabilities(settings.ADDONS_AVAILABLE)


def attach_handlers(app, settings):
    """Add callback handlers to ``app`` in the correct order."""
    # Add callback handlers to application
    add_handlers(app, mongo_handlers.handlers)
    add_handlers(app, celery_task_handlers.handlers)
    add_handlers(app, transaction_handlers.handlers)
    add_handlers(app, postcommit_handlers.handlers)

    # Attach handler for checking view-only link keys.
    # NOTE: This must be attached AFTER the TokuMX to avoid calling
    # a commitTransaction (in toku's after_request handler) when no transaction
    # has been created
    add_handlers(app, {'before_request': framework.sessions.prepare_private_key})
    # framework.session's before_request handler must go after
    # prepare_private_key, else view-only links won't work
    add_handlers(app, {'before_request': framework.sessions.before_request,
                       'after_request': framework.sessions.after_request})

    return app


def do_set_backends(settings):
    logger.debug('Setting storage backends')
    maintenance.ensure_maintenance_collection()
    set_up_storage(
        website.models.MODELS,
        storage.MongoStorage,
        addons=settings.ADDONS_AVAILABLE,
    )


def init_app(settings_module='website.settings', set_backends=True, routes=True,
             attach_request_handlers=True):
    """Initializes the OSF. A sort of pseudo-app factory that allows you to
    bind settings, set up routing, and set storage backends, but only acts on
    a single app instance (rather than creating multiple instances).

    :param settings_module: A string, the settings module to use.
    :param set_backends: Whether to set the database storage backends.
    :param routes: Whether to set the url map.

    """
    # The settings module
    settings = importlib.import_module(settings_module)

    init_addons(settings, routes)
    with open(os.path.join(settings.STATIC_FOLDER, 'built', 'nodeCategories.json'), 'wb') as fp:
        json.dump(settings.NODE_CATEGORY_MAP, fp)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.base.settings')
    django.setup()

    app.debug = settings.DEBUG_MODE

    # default config for flask app, however, this does not affect setting cookie using set_cookie()
    app.config['SESSION_COOKIE_SECURE'] = settings.SESSION_COOKIE_SECURE
    app.config['SESSION_COOKIE_HTTPONLY'] = settings.SESSION_COOKIE_HTTPONLY

    if set_backends:
        do_set_backends(settings)
    if routes:
        try:
            make_url_map(app)
        except AssertionError:  # Route map has already been created
            pass

    if attach_request_handlers:
        attach_handlers(app, settings)

    if app.debug:
        logger.info("Sentry disabled; Flask's debug mode enabled")
    else:
        sentry.init_app(app)
        logger.info("Sentry enabled; Flask's debug mode disabled")

    if set_backends:
        ensure_schemas()
        ensure_licenses()
        ensure_taxonomies()
    apply_middlewares(app, settings)

    return app


def apply_middlewares(flask_app, settings):
    # Use ProxyFix to respect X-Forwarded-Proto header
    # https://stackoverflow.com/questions/23347387/x-forwarded-proto-and-flask
    if settings.LOAD_BALANCER:
        flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app)

    return flask_app
